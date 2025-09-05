from datetime import datetime, timedelta

from draft import n
class A(object):
    def __init__(self,x):
        self.x = x



class B(A):
    def __init__(self):
        A.__init__()
