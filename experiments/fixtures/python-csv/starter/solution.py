def parse_counts(text):
    lines=text.splitlines()
    if not lines or lines[0] != 'name,count': raise ValueError('header')
    rows=[]
    for line in lines[1:]:
        name,count=line.split(',')
        rows.append({'name':name,'count':int(count)})
    return {'rows':rows,'errors':[]}
