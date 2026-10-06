import sys,json
def pairs(items):
    d={}
    for k,v in items:
        if k in d: raise ValueError('duplicate')
        d[k]=v
    return d
def reject(x): raise ValueError('nonfinite')
def main():
    names=[];total=0
    try:
        text=sys.stdin.buffer.read().decode('utf-8-sig')
        for line in text.splitlines():
            if not line.strip():continue
            r=json.loads(line,object_pairs_hook=pairs,parse_constant=reject)
            if type(r)!=dict or set(r)!={'name','count'} or type(r['name'])!=str or not r['name'] or type(r['count'])!=int or not 0<=r['count']<=1000000:raise ValueError('record')
            names.append(r['name']);total+=r['count']
        out=(json.dumps({'total':total,'names':names},ensure_ascii=False)+'\n').encode('utf8')
    except (ValueError,UnicodeError,TypeError):
        sys.stderr.buffer.write(b'invalid input\n');return 2
    sys.stdout.buffer.write(out);return 0
if __name__=='__main__':sys.exit(main())
