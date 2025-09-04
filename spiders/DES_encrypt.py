from Crypto.Cipher import DES
from Crypto.Util.Padding import unpad
import base64


def decrypt_by_des(ciphertext, key):
    """
    使用DES算法解密Base64编码的密文

    Args:
        ciphertext (str): Base64编码的密文
        key (str): 密钥字符串

    Returns:
        str: 解密后的明文
    """
    try:
        # 将Base64编码的密文解码为字节
        cipher_bytes = base64.b64decode(ciphertext)

        # 将密钥转换为字节，DES要求密钥长度为8字节
        key_bytes = key.encode('utf-8')[:8]  # 截取前8字节
        if len(key_bytes) < 8:
            # 如果密钥不足8字节，用0填充
            key_bytes = key_bytes.ljust(8, b'\x00')

        # 创建DES解密器（ECB模式）
        cipher = DES.new(key_bytes, DES.MODE_ECB)

        # 解密
        decrypted_bytes = cipher.decrypt(cipher_bytes)

        # 去除PKCS7填充
        decrypted_bytes = unpad(decrypted_bytes, DES.block_size)

        # 转换为UTF-8字符串
        return decrypted_bytes.decode('utf-8')

    except Exception as e:
        print(f"解密失败: {e}")
        return None


def str_key():
    """
    返回密钥字符串

    Returns:
        str: 密钥
    """
    key = "Ctpsp@884*".strip()  # 对应JavaScript中的$.trim()
    return key


# 使用示例
if __name__ == "__main__":
    # 获取密钥
    key = str_key()

    # 示例密文（需要替换为实际的Base64编码密文）
    ciphertext = "你的Base64密文"

    # 解密
    result = decrypt_by_des(ciphertext, key)

    if result:
        print(f"解密结果: {result}")
    else:
        print("解密失败")