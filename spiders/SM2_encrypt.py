import json
import hashlib
import secrets
from typing import Union, List
from gmssl import sm2


def analyze_with_real_data():
    """使用真实数据分析加密结果"""
    # 真实的原始数据
    real_data = {
        "platformCode": "",
        "noticeName": "",
        "tradeType": "2",
        "link": "PROJECT",
        "pageSize": 10,
        "page": 3,
        "important": "",
        "remote": ""
    }

    # 成功的加密结果
    successful_result = "04996b6e3e08cfae8656d307760fd4d349af57fa85540a826bdf08c083d7b001c978c5be444e01ec47e1a91a0dae347e99d2f6ec768acbc694e1775e8d961e013326afd7c48f84729304144b2b0ba47ac4b1c0948ee988f6bbd7c0a3907c0cfabb25c39b71b83b7ddc6af3d4c3de781ab5a58385f5ed6663120eaa6517a2fc84bbbfeaa1aaeea4146b434a706be3161c67e0124e03945bd08cd4c591d2ec67f12d1557f5398bc661003d1da9aa941453cc20adf595d4c5d89e063cc1e9a29f9de36b984fb77c062f9812aff587a8bfa3a59595990dd378"

    # 转换为JSON字符串（关键：要与JS完全一致）
    json_str = json.dumps(real_data, separators=(',', ':'), ensure_ascii=False)
    print("=== 真实数据分析 ===")
    print(f"原始JSON: {json_str}")
    print(f"JSON字节数: {len(json_str.encode('utf-8'))}")
    print(f"JSON十六进制: {json_str.encode('utf-8').hex()}")

    # 分析成功的加密结果
    print(f"\n=== 成功加密结果分析 ===")
    print(f"总长度: {len(successful_result)}")

    # 去掉04前缀
    data = successful_result[2:]
    print(f"去掉04前缀后长度: {len(data)}")

    # SM2标准格式分析: C1(128) + C3(64) + C2(密文)
    c1 = data[:128]  # 临时公钥点
    c3 = data[128:192]  # SM3哈希值
    c2 = data[192:]  # 密文

    print(f"C1 (临时公钥): {c1}")
    print(f"C1 长度: {len(c1)} 字符 = {len(c1) // 2} 字节")

    print(f"C3 (哈希值): {c3}")
    print(f"C3 长度: {len(c3)} 字符 = {len(c3) // 2} 字节")

    print(f"C2 (密文): {c2}")
    print(f"C2 长度: {len(c2)} 字符 = {len(c2) // 2} 字节")

    # 验证密文长度是否匹配原始数据
    expected_cipher_len = len(json_str.encode('utf-8'))
    actual_cipher_len = len(c2) // 2

    print(f"\n=== 长度验证 ===")
    print(f"原始数据字节数: {expected_cipher_len}")
    print(f"密文字节数: {actual_cipher_len}")
    print(f"长度匹配: {'✅' if expected_cipher_len == actual_cipher_len else '❌'}")

    return {
        'json_str': json_str,
        'json_bytes': json_str.encode('utf-8'),
        'c1': c1,
        'c3': c3,
        'c2': c2,
        'total_len': len(successful_result)
    }


class AccurateSM2Crypto:
    """精确复现JS加密逻辑的SM2实现"""

    def __init__(self):
        # SM2椭圆曲线参数
        self.p = 0xFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00000000FFFFFFFFFFFFFFFF
        self.a = 0xFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00000000FFFFFFFFFFFFFFFC
        self.b = 0x28E9FA9E9D9F5E344D5A9E4BCF6509A7F39789F515AB8F92DDBCBD414D940E93
        self.n = 0xFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFF7203DF6B21C6052B53BBF40939D54123
        self.gx = 0x32C4AE2C1F1981195F9904466A39C9948FE30BBFF2660BE1715A4589334C74C7
        self.gy = 0xBC3736A2F4F6779C59BDCEE36B692153D0A9877CC62A474002DF32E52139F0A0

        self.public_key = "03702057B53C16031D786D9E06D839163F3DD5867E6E161292F61E1340FDF6DE24"

    def get_encrypted(self, message: str) -> str:
        """
        精确复现 getEncrypted: e => "04" + bn.sm2.doEncrypt(e, "公钥", 1)
        """
        # print(f"开始加密消息: {message}")

        try:
            # 优先使用gmssl库
            return self._encrypt_with_gmssl_precise(message)
        except Exception as e:
            print(f"gmssl加密失败，使用自定义实现: {e}")
            return self._encrypt_custom_precise(message)

    def _encrypt_with_gmssl_precise(self, message: str) -> str:
        """使用gmssl库的精确实现"""
        try:

            # 解压缩公钥
            full_public_key = self._decompress_public_key(self.public_key)
            # print(f"解压后公钥: {full_public_key}")

            # 创建SM2加密对象
            sm2_crypt = sm2.CryptSM2(public_key=full_public_key, private_key="B8FDD61FD8C115F51C6E23431614A204EE7C59FB2E0C58FFE58F786790793EC4", mode=1)

            # 消息转字节
            message_bytes = message.encode('utf-8')
            # print(f"消息字节长度: {len(message_bytes)}")
            # print(f"消息字节内容: {message_bytes.hex()}")

            # 执行加密
            encrypted_data = sm2_crypt.encrypt(message_bytes)
            encrypted_hex = encrypted_data.hex()

            # print(f"gmssl加密结果长度: {len(encrypted_hex)}")

            # 添加04前缀
            result = "04" + encrypted_hex
            # print(f"最终结果长度: {len(result)}")

            return result

        except ImportError:
            raise Exception("需要安装gmssl库: pip install gmssl")
        except Exception as e:
            raise Exception(f"gmssl加密错误: {e}")

    def _encrypt_custom_precise(self, message: str) -> str:
        """自定义精确SM2实现"""
        print("使用自定义SM2加密...")

        # 消息处理
        message_bytes = message.encode('utf-8')
        message_list = list(message_bytes)
        print(f"消息字节数组: {message_list}")

        # 解析公钥
        pub_point = self._decompress_public_key_to_point(self.public_key)
        print(f"公钥点: x={hex(pub_point[0])[:20]}..., y={hex(pub_point[1])[:20]}...")

        # 生成临时密钥对（严格按照JS逻辑）
        temp_keypair = self._generate_keypair_like_js()
        temp_private = temp_keypair['private']
        temp_public_hex = temp_keypair['public']

        print(f"临时私钥: {hex(temp_private)[:20]}...")
        print(f"临时公钥: {temp_public_hex[:40]}...")

        # 如果临时公钥长度>128，取后128位（对应JS逻辑）
        if len(temp_public_hex) > 128:
            temp_public_hex = temp_public_hex[-128:]
            print(f"截取后的临时公钥: {temp_public_hex[:40]}...")

        # 计算共享点 S = temp_private * pub_point
        shared_point = self._point_multiply(temp_private, pub_point)
        shared_x = format(shared_point[0], '064x')
        shared_y = format(shared_point[1], '064x')

        print(f"共享点x: {shared_x[:20]}...")
        print(f"共享点y: {shared_y[:20]}...")

        # 转换为字节数组（对应JS的hexToArray）
        x_bytes = [int(shared_x[i:i + 2], 16) for i in range(0, len(shared_x), 2)]
        y_bytes = [int(shared_y[i:i + 2], 16) for i in range(0, len(shared_y), 2)]

        # 计算消息认证码 s = Hash(x_bytes + message_list + y_bytes)
        mac_input = x_bytes + message_list + y_bytes
        mac_hex = self._hash_function(mac_input)
        print(f"MAC: {mac_hex}")

        # KDF密钥派生（严格按照JS逻辑）
        keystream = self._kdf_like_js(x_bytes, y_bytes, len(message_list))
        print(f"密钥流前10字节: {keystream[:10]}")

        # 加密消息：message XOR keystream
        encrypted_message = []
        for i in range(len(message_list)):
            encrypted_byte = message_list[i] ^ (keystream[i] & 0xff)
            encrypted_message.append(encrypted_byte)

        encrypted_hex = ''.join(f'{b:02x}' for b in encrypted_message)
        print(f"加密后的消息: {encrypted_hex}")

        # 组合最终结果：04 + temp_public + mac + encrypted_message (mode=1)
        result = "04" + temp_public_hex + mac_hex + encrypted_hex
        print(f"最终组合结果长度: {len(result)}")

        return result

    def _decompress_public_key(self, compressed_key: str) -> str:
        """解压公钥为完整十六进制字符串"""
        point = self._decompress_public_key_to_point(compressed_key)
        x_hex = format(point[0], '064x')
        y_hex = format(point[1], '064x')
        return x_hex + y_hex

    def _decompress_public_key_to_point(self, compressed_key: str) -> tuple:
        """解压公钥为坐标点"""
        if not compressed_key.startswith(('02', '03')):
            raise ValueError(f"不是压缩公钥格式: {compressed_key[:10]}")

        y_is_odd = compressed_key.startswith('03')
        x = int(compressed_key[2:], 16)

        # 计算y² = x³ + ax + b (mod p)
        y_squared = (pow(x, 3, self.p) + self.a * x + self.b) % self.p

        # 计算y = √(y²) (mod p)
        y = pow(y_squared, (self.p + 1) // 4, self.p)

        # 选择正确的y值
        if (y % 2) != y_is_odd:
            y = self.p - y

        return (x, y)

    def _generate_keypair_like_js(self) -> dict:
        """模拟JS的generateKeyPairHex()"""
        # 生成私钥
        private_key = secrets.randbelow(self.n - 1) + 1

        # 计算公钥点
        public_point = self._point_multiply(private_key, (self.gx, self.gy))

        # 格式化为十六进制
        private_hex = format(private_key, '064x')
        public_x_hex = format(public_point[0], '064x')
        public_y_hex = format(public_point[1], '064x')
        public_hex = '04' + public_x_hex + public_y_hex

        return {
            'private': private_key,
            'public': public_hex
        }

    def _point_multiply(self, k: int, point: tuple) -> tuple:
        """椭圆曲线点乘法"""
        if k == 0:
            return None

        def mod_inverse(a, m):
            return pow(a, m - 2, m)

        def point_add(p1, p2):
            if p1 is None: return p2
            if p2 is None: return p1

            x1, y1 = p1
            x2, y2 = p2

            if x1 == x2:
                if y1 == y2:
                    # 点倍增
                    s = (3 * x1 * x1 + self.a) * mod_inverse(2 * y1, self.p) % self.p
                else:
                    return None
            else:
                s = (y2 - y1) * mod_inverse(x2 - x1, self.p) % self.p

            x3 = (s * s - x1 - x2) % self.p
            y3 = (s * (x1 - x3) - y1) % self.p

            return (x3, y3)

        # 二进制方法
        result = None
        addend = point

        while k:
            if k & 1:
                result = point_add(result, addend)
            addend = point_add(addend, addend)
            k >>= 1

        return result

    def _kdf_like_js(self, x_bytes: List[int], y_bytes: List[int], keylen: int) -> List[int]:
        """严格按照JS逻辑的KDF实现"""
        counter = 1
        keystream_pos = 0
        keystream = []

        # m = [].concat(x_bytes, y_bytes)
        m = x_bytes + y_bytes

        def generate_keystream():
            nonlocal keystream, counter, keystream_pos
            # JS: [...m, p >> 24 & 255, p >> 16 & 255, p >> 8 & 255, 255 & p]
            counter_bytes = [
                (counter >> 24) & 255,
                (counter >> 16) & 255,
                (counter >> 8) & 255,
                counter & 255
            ]
            hash_input = m + counter_bytes
            hash_hex = self._hash_function(hash_input)
            # 转换为字节数组
            keystream = [int(hash_hex[i:i + 2], 16) for i in range(0, len(hash_hex), 2)]
            counter += 1
            keystream_pos = 0

        # 初始生成
        generate_keystream()

        # 生成所需长度的密钥流
        result = []
        for i in range(keylen):
            if keystream_pos >= len(keystream):
                generate_keystream()
            result.append(keystream[keystream_pos])
            keystream_pos += 1

        return result

    def _hash_function(self, data: List[int]) -> str:
        """哈希函数（对应JS的Za函数）"""
        try:
            # 尝试使用SM3
            from gmssl.sm3 import sm3_hash
            return sm3_hash(data)
        except ImportError:
            # 回退到SHA256
            print("警告: 使用SHA256替代SM3")
            return hashlib.sha256(bytes(data)).hexdigest()


def test_with_real_data():
    """使用真实数据测试"""
    print("=== 使用真实数据测试加密 ===")

    # 分析真实数据
    analysis = analyze_with_real_data()

    # 创建加密器
    crypto = AccurateSM2Crypto()

    # 测试加密
    json_str = analysis['json_str']

    try:
        encrypted = crypto.get_encrypted(json_str)
        print(f"\n=== 加密结果对比 ===")
        print(f"成功结果: {analysis['total_len']} 字符")
        print(f"我的结果: {len(encrypted)} 字符")
        print(f"长度匹配: {'✅' if len(encrypted) == analysis['total_len'] else '❌'}")

        print(f"\n成功结果: {analysis['c1'] + analysis['c3'] + analysis['c2']}")
        print(f"我的结果:   {encrypted}")

        if encrypted.startswith('04'):
            my_data = encrypted[2:]
            my_c1 = my_data[:128]
            my_c3 = my_data[128:192] if len(my_data) > 192 else ""
            my_c2 = my_data[192:] if len(my_data) > 192 else ""

            print(f"\n结构对比:")
            print(f"C1匹配: {'✅' if my_c1 == analysis['c1'] else '❌'}")
            print(f"C3匹配: {'✅' if my_c3 == analysis['c3'] else '❌'}")
            print(f"C2匹配: {'✅' if my_c2 == analysis['c2'] else '❌'}")

            if my_c1 != analysis['c1']:
                print(f"预期C1: {analysis['c1'][:40]}...")
                print(f"实际C1: {my_c1[:40]}...")

        return encrypted

    except Exception as e:
        print(f"加密测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    print("请确保安装: pip install gmssl")
    print("=" * 80)

    # 分析真实数据和成功结果
    analyze_with_real_data()

    print("\n" + "=" * 80)

    # 测试加密实现
    result = test_with_real_data()

    if result:
        print(f"\n最终加密结果:")
        print(result)
    else:
        print("\n加密失败，请检查实现")


if __name__ == "__main__":
    main()
