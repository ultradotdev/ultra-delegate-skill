import csv, io, re
def parse_counts(text):
    try: records=list(csv.reader(io.StringIO(text.removeprefix('\ufeff'),newline=''),strict=True))
    except csv.Error as e: raise ValueError('csv') from e
    records=[r for r in records if r]
    if not records or records[0]!=['name','count']: raise ValueError('header')
    rows=[];errors=[]
    for i,r in enumerate(records[1:],1):
        if len(r)!=2 or not r[0] or not re.fullmatch('[0-9]+',r[1].strip(' \t')):
            errors.append(i);continue
        n=r[1].strip(' \t').lstrip('0') or '0'
        if len(n)>7 or int(n)>1000000: errors.append(i);continue
        rows.append({'name':r[0],'count':int(n)})
    return {'rows':rows,'errors':errors}
