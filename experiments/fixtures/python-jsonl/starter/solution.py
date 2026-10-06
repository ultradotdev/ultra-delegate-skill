import sys,json
names=[];total=0
for line in sys.stdin:
    row=json.loads(line)
    names.append(row['name']);total+=row['count']
    print(json.dumps({'total':total,'names':names}))
