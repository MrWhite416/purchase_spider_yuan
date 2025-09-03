
from datetime import date,datetime

t = "2025-09-02 12:05"[:10]
s = datetime.strptime(t,"%Y-%m-%d").date()
print(s)