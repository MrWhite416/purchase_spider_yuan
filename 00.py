from lxml import etree

e = """<li>
                                    <a href="http://www.ccgp.gov.cn/cggg/dfgg/cjgg/202508/t20250829_25257111.htm" style="line-height:18px" target="_blank">
                                        西安市雁塔区电子城社区卫生服务中心2025年西安市红会医院<font color="red">卫星</font>医院（电子城）医用设备采购中标（成交）结果公告
                                    </a>

                                    <p>一、项目编号：JN-DZCWSZX-0250812二、项目名称：2025年西安市红会医院卫星医院（电子城）医用设备采购三、采购结果合同包1(2025年西安市红会医院卫星医院（电子城）医用设备采购):供应商名称供应商地址评审方法是否</p>
                                    <span>2025.08.29 15:04:16
                                        | 采购人：西安市雁塔区电子城社区卫生服务中心
                                        | 代理机构：陕西杰诺招标有限公司
                                        <br>
                                        <strong style="font-weight:bolder">
                                            
                                            
                                                成交公告
                                            
                                        </strong>
                                        | 陕西
                                        | <strong style="font-weight:bolder"> </strong>
                                        
                                    </span>
                                </li>"""

sele = etree.HTML(e)
li = sele.xpath(".//li")[0]
text = li.xpath("./span/text()")[0]
print(text)
