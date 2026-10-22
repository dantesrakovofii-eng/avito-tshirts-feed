import csv, sys, re, os
from pathlib import Path
from datetime import date
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
TEMPLATE_FIELDS = ['Id','DateBegin','DateEnd','ListingFee','AdStatus','AvitoId','ManagerName','ContactPhone','Address','Latitude','Longitude','SellerAddressID','Images','VideoURL','ContactMethod','Promo','PromoAutoOptions','PromoManualOptions','Title','Description','Category','InternetCalls','CallsDevices','Delivery','WeightForDelivery','LengthForDelivery','HeightForDelivery','WidthForDelivery','ReturnPolicy','TryOn','DeliverySubsidy','TNVED','OKPD2','NoDocuments','SquareSymbol','CodeGTIN','Certificate','Declaration','SGR','DateSGR','UrlSGR','Minselhoz','DateMinselhoz','NumberRU','DateRU','BarcodeAvailability','Price','GoodsType','Condition','Season','AdType','Brand','Color','ColorName','MaterialsOdezhda','VideoFileURL','MultiItem','MultiName','Apparel','Size','GoodsSubType','WholesaleType','WholesaleMinOrderType','WholesaleMinOrderCount','WholesalePacking','WholesalePackingCount','WholesaleMeasureUnit','WholesaleDiscountLadderType','DiscountLadderList']
# Категориальные перечисления нужно сверить с требованиями Авито. Это проверка заполнения, не гарантия прохождения модерации.
REQUIRED=['Id','Title','Description','Category','GoodsType','Price','Address','Condition','Size','ImageURLs']
APPROVED={'одобрено','approved'}

def generate(today=None):
    today = today or date.today()
    with (ROOT/'catalog.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    scheduled=[]; errors=[]; seen=set(); counts={}
    for i, r in enumerate(rows,2):
        if (r.get('Status') or '').strip().lower() not in APPROVED: continue
        rid=(r.get('Id') or '').strip()
        if rid in seen: errors.append(f'Повтор ID: {rid}'); continue
        seen.add(rid)
        missing=[x for x in REQUIRED if not (r.get(x) or '').strip()]
        if missing: errors.append(f'Строка {i} ({rid}): пусто {", ".join(missing)}'); continue
        try:
            d=date.fromisoformat(r['DateBegin'].strip())
            p=int(r['Price'].strip())
            if p<=0: raise ValueError()
        except ValueError:
            errors.append(f'Строка {i} ({rid}): некорректная дата YYYY-MM-DD или цена'); continue
        urls=[x.strip() for x in r['ImageURLs'].split('|') if x.strip()]
        if any((urlparse(x).scheme!='https' or not urlparse(x).netloc) for x in urls):
            errors.append(f'Строка {i} ({rid}): нужны прямые HTTPS-ссылки на фото'); continue
        counts[d]=counts.get(d,0)+1
        if d<=today: scheduled.append((r,urls))
    for d,n in counts.items():
        if n>4: errors.append(f'{d}: {n} одобренных объявлений, лимит 4 новых в день')
    if errors: raise ValueError('\n'.join(errors))
    if not scheduled: raise ValueError('Нет одобренных карточек с датой размещения не позже сегодня: публикация блокируется')
    ads=ET.Element('Ads',{'formatVersion':'3','target':'Avito.ru'})
    for row,urls in scheduled:
        ad=ET.SubElement(ads,'Ad')
        for field in TEMPLATE_FIELDS:
            if field=='Images':
                images=ET.SubElement(ad,'Images')
                for url in urls: ET.SubElement(images,'Image',{'url':url})
            elif field in row and (row[field] or '').strip():
                ET.SubElement(ad,field).text=row[field].strip()
    ET.indent(ads,space='  ')
    site=ROOT/'site';site.mkdir(exist_ok=True)
    ET.ElementTree(ads).write(site/'catalog.xml',encoding='utf-8',xml_declaration=True)
    (site/'index.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Avito feed</title><body><p>Avito XML feed</p><p><a href="catalog.xml">catalog.xml</a></p></body></html>',encoding='utf-8')
    (site/'.nojekyll').touch()
    print(f'Подготовлено {len(scheduled)} объявлений, XML в site/catalog.xml')

if __name__=='__main__':
    try: generate()
    except ValueError as e:
        print('Фид не обновлён: '+str(e),file=sys.stderr)
        sys.exit(1)
