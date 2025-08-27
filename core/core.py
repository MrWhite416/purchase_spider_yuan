# development time: 2025-08-27  11:37
# developer: 元英

import functools
from typing import Type, Callable


class ExceptionHandlerMeta(type):
    """
    元类：为所有继承它的类的方法统一添加异常捕获
    """
    # 可通过类属性自定义捕获的异常类型和处理函数
    exception_classes: tuple[Type[Exception], ...] = (Exception,)
    exception_handler: Callable[[Exception], None] = None

    def __new__(cls, name: str, bases: tuple, namespace: dict):
        # 1. 创建类之前，遍历命名空间中的所有方法
        for attr_name, attr_value in namespace.items():
            # 只处理实例方法（排除特殊方法、类方法、静态方法）
            if callable(attr_value) and not attr_name.startswith("__"):
                # 2. 用包装函数添加异常捕获
                original_method = attr_value

                @functools.wraps(original_method)
                def wrapper(*args, **kwargs):
                    try:
                        # 调用原方法
                        return original_method(*args, **kwargs)
                    except Exception as e:
                        print(f"方法 {original_method.__name__} 抛出异常：{type(e).__name__} - {e} - 行号：{e.__traceback__.tb_lineno}")

                # 3. 替换原方法为包装后的方法
                namespace[attr_name] = wrapper

        # 4. 创建并返回新类
        return super().__new__(cls, name, bases, namespace)

