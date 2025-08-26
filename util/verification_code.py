# development time: 2025-08-21  16:59
# developer: 元英

import ddddocr


def ocr_code(img_bytes: bytes):
    """
    识别验证码
    :param img_path:
    :return:
    """

    ocr = ddddocr.DdddOcr(show_ad=False)

    # 进行识别
    result = ocr.classification(img_bytes)
    return result

