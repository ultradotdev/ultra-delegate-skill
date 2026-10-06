"""Frozen private fixtures and independent checks. Never copy this file to workers."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

FIXTURES={
'python-csv':dict(file='solution.py',
contract='''Fix parse_counts(text: str) -> dict in solution.py. Input is CSV with exactly the header name,count. Accept LF or CRLF, a leading Unicode BOM, quoted commas, doubled quotes and embedded newlines. Ignore completely blank physical lines. Each logical data record must have exactly two columns; name must be nonempty but preserve its whitespace. Count must consist only of ASCII digits, optionally surrounded by spaces/tabs, represent 0..1000000, and exclude signs, exponents and non-ASCII digits. Return {"rows": [{"name": str, "count": int}, ...], "errors": [logical data record index, ...]}; indices start at 1 and ignore blank lines. Preserve valid row order and report bad rows without losing later records. Invalid/missing header or malformed CSV raises ValueError. Only edit solution.py; standard library only.''',
starter='''def parse_counts(text):
    lines=text.splitlines()
    if not lines or lines[0] != 'name,count': raise ValueError('header')
    rows=[]
    for line in lines[1:]:
        name,count=line.split(',')
        rows.append({'name':name,'count':int(count)})
    return {'rows':rows,'errors':[]}
''',
reference='''import csv, io, re
def parse_counts(text):
    try: records=list(csv.reader(io.StringIO(text.removeprefix('\\ufeff'),newline=''),strict=True))
    except csv.Error as e: raise ValueError('csv') from e
    records=[r for r in records if r]
    if not records or records[0]!=['name','count']: raise ValueError('header')
    rows=[];errors=[]
    for i,r in enumerate(records[1:],1):
        if len(r)!=2 or not r[0] or not re.fullmatch('[0-9]+',r[1].strip(' \\t')):
            errors.append(i);continue
        n=r[1].strip(' \\t').lstrip('0') or '0'
        if len(n)>7 or int(n)>1000000: errors.append(i);continue
        rows.append({'name':r[0],'count':int(n)})
    return {'rows':rows,'errors':errors}
''',
checks='''import importlib.util,sys
s=importlib.util.spec_from_file_location('subject',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
f=m.parse_counts
assert f('name,count\\na,2\\nb,0\\n')=={'rows':[{'name':'a','count':2},{'name':'b','count':0}],'errors':[]}
assert f('\\ufeffname,count\\r\\n"a,b",3\\r\\n"a""b",4\\r\\n"two\\r\\nlines",5\\r\\n')=={'rows':[{'name':'a,b','count':3},{'name':'a"b','count':4},{'name':'two\\r\\nlines','count':5}],'errors':[]}
assert f('name,count\\n\\nbad,-1\\nx,2,3\\n,2\\ny,+2\\nz,١\\n q , \\t0007\\t \\nend,1000000\\n')=={'rows':[{'name':' q ','count':7},{'name':'end','count':1000000}],'errors':[1,2,3,4,5]}
assert f('name,count\\na,'+'9'*5000+'\\nb,'+'0'*5000+'2\\nc,1000001\\n')=={'rows':[{'name':'b','count':2}],'errors':[1,3]}
for bad in ['', 'wrong,count\\na,1', 'name,count\\n"unclosed,1']:
 try:f(bad)
 except ValueError:pass
 else:raise AssertionError('must reject header/malformed CSV')
'''),
'python-jsonl':dict(file='solution.py',
contract='''Fix the CLI solution.py. Read UTF-8 JSON Lines bytes from stdin (optional initial UTF-8 BOM); ignore blank lines. Every nonblank line must be a JSON object with exactly string "name" and integer "count" keys. Name is nonempty and count is 0..1000000, booleans are not integers. Duplicate JSON keys, nonfinite JSON literals, invalid UTF-8 or any malformed/out-of-contract record are invalid. On complete valid input emit one UTF-8 JSON object {"total": sum(count), "names": [names in order]} followed by LF, exit 0. Empty input yields total 0 and empty names. On ANY invalid input emit no stdout bytes, a nonempty diagnostic on stderr, exit 2. Valid output is independent of PYTHONIOENCODING. Only edit solution.py; standard library only.''',
starter='''import sys,json
names=[];total=0
for line in sys.stdin:
    row=json.loads(line)
    names.append(row['name']);total+=row['count']
    print(json.dumps({'total':total,'names':names}))
''',
reference='''import sys,json
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
        out=(json.dumps({'total':total,'names':names},ensure_ascii=False)+'\\n').encode('utf8')
    except (ValueError,UnicodeError,TypeError):
        sys.stderr.buffer.write(b'invalid input\\n');return 2
    sys.stdout.buffer.write(out);return 0
if __name__=='__main__':sys.exit(main())
''',
checks='''import subprocess,sys,json,os
p=sys.argv[1]
def run(b):
 env=dict(os.environ,PYTHONIOENCODING='latin1');return subprocess.run([sys.executable,p],input=b,capture_output=True,env=env,timeout=5)
for b,want in [(b'',{'total':0,'names':[]}),(b' \\n\\n',{'total':0,'names':[]}),(b'\\xef\\xbb\\xbf'+('{"name":"雪","count":2}\\n{"name":"a","count":0}\\n').encode(),{'total':2,'names':['雪','a']}),(b'{"name":"a","count":1000000}\\n{"name":"a","count":3}',{'total':1000003,'names':['a','a']})]:
 r=run(b);assert r.returncode==0,(r.returncode,r.stderr);assert r.stdout.endswith(b'\\n');assert json.loads(r.stdout)==want
prefix=b'{"name":"ok","count":1}\\n'
for b in [b'[]',b'null',b'{"name":"a","count":true}',b'{"name":"","count":0}',b'{"name":"a","count":1.0}',b'{"name":"a","count":-1}',b'{"name":"a","count":1000001}',b'{"name":"a","count":1,"count":2}',b'{"name":"a","count":NaN}',b'{"name":"a","count":1,"extra":0}',b'{',b'\\xff',b'{"name":"a","count":'+b'9'*5000+b'}']:
 r=run(prefix+b);assert r.returncode==2,(b[:80],r.returncode);assert r.stdout==b'',b[:80];assert r.stderr
'''),
 'typescript-options':dict(file='solution.ts',
contract='''Fix exported normalizeOptions(value: unknown) in solution.ts. Accept only a non-null plain object (prototype Object.prototype or null), never an array. Own enumerable keys may only be limit, offset, label. Missing or undefined fields default to limit 20, offset 0, label "". limit must be a finite integer 1..100, offset a nonnegative safe integer, label a string at most 40 UTF-16 code units. No coercion. Return a fresh {limit, offset, label} with no mutation. Invalid input throws TypeError. Inherited values must not supply field values; own keys with names such as __proto__ or constructor are unknown and invalid. Only edit solution.ts. No dependencies. Node supports native TypeScript stripping.''',
starter='''export function normalizeOptions(value: any) {
 return {limit: Number(value.limit || 20),offset: Number(value.offset || 0),label: String(value.label || '')};
}
''',
reference='''export function normalizeOptions(value: unknown) {
 if(value===null || typeof value!=='object' || ![Object.prototype,null].includes(Object.getPrototypeOf(value))) throw new TypeError('object');
 const x=value as Record<string,unknown>;
 if(Object.keys(x).some(k=>!['limit','offset','label'].includes(k))) throw new TypeError('key');
 const field=(k:string,d:unknown)=>Object.hasOwn(x,k)&&x[k]!==undefined?x[k]:d;
 const limit=field('limit',20),offset=field('offset',0),label=field('label','');
 if(typeof limit!=='number'||!Number.isInteger(limit)||limit<1||limit>100 || typeof offset!=='number'||!Number.isSafeInteger(offset)||offset<0 || typeof label!=='string'||label.length>40)throw new TypeError('field');
 return {limit,offset,label};
}
''',
checks='''import assert from 'node:assert/strict';import {pathToFileURL} from 'node:url';
const {normalizeOptions:f}=await import(pathToFileURL(process.argv[1]).href);
assert.deepEqual(f({}),{limit:20,offset:0,label:''});assert.deepEqual(f({limit:1,offset:0,label:'雪'}),{limit:1,offset:0,label:'雪'});
const x=Object.freeze({limit:100,offset:Number.MAX_SAFE_INTEGER,label:'a'.repeat(40)});assert.deepEqual(f(x),x);assert.notEqual(f(x),x);
assert.deepEqual(f(Object.assign(Object.create(null),{limit:undefined})),{limit:20,offset:0,label:''});
for(const bad of [null,[],3,'x',new Date(),{limit:0},{limit:'2'},{limit:NaN},{limit:Infinity},{limit:1.5},{limit:101},{offset:-1},{offset:2**53},{offset:'0'},{label:null},{label:'😀'.repeat(21)},{unexpected:1},JSON.parse('{"__proto__":{}}'),{constructor:1},Object.create({limit:2})])assert.throws(()=>f(bad),TypeError);
'''),
 'typescript-state':dict(file='solution.ts',
contract='''Fix exported applyBatch(state, operations) in solution.ts. State is a valid array of unique {id: nonempty string, count: nonnegative safe integer} items. Operations are unknown input: must be an array of plain objects with exact own enumerable keys: {type:"put", id, count}, or {type:"remove", id}. Each id is a nonempty string; put count is a nonnegative safe integer, no coercion. Reject invalid operations, missing/extra keys, arrays or class instances with TypeError. Apply all operations sequentially to a fresh result without mutating state, operations or existing item objects; no partial mutation on failure. put replaces an existing item in its current position, appends new ids; remove deletes an existing id and is a no-op for unknown ids. A removed id later put appends at the end. Treat every string id literally including __proto__ and constructor. Return independent item objects even for untouched state entries. Only edit solution.ts; no dependencies.''',
starter='''export function applyBatch(state: any[], operations: any) {
 for(const op of operations){
  const i=state.findIndex(x=>x.id===op.id);
  if(op.type==='remove'){if(i>=0)state.splice(i,1);}
  else if(i>=0)state[i].count=op.count;
  else state.push({id:op.id,count:op.count});
 }
 return state;
}
''',
reference='''export function applyBatch(state: {id:string,count:number}[], operations: unknown) {
 if(!Array.isArray(operations))throw new TypeError('operations');
 const result=state.map(x=>({...x}));
 for(const op of operations){
  if(op===null||typeof op!=='object'||![Object.prototype,null].includes(Object.getPrototypeOf(op)))throw new TypeError('operation');
  const keys=Object.keys(op).sort();
  const expected=op.type==='put'?['count','id','type']:op.type==='remove'?['id','type']:[];
  if(JSON.stringify(keys)!==JSON.stringify(expected)||typeof op.id!=='string'||!op.id||op.type==='put'&&(!Number.isSafeInteger(op.count)||op.count<0))throw new TypeError('fields');
  const i=result.findIndex(x=>x.id===op.id);
  if(op.type==='remove'){if(i>=0)result.splice(i,1);}
  else if(i>=0)result[i]={id:op.id,count:op.count};else result.push({id:op.id,count:op.count});
 }
 return result;
}
''',
checks='''import assert from 'node:assert/strict';import {pathToFileURL} from 'node:url';
const {applyBatch:f}=await import(pathToFileURL(process.argv[1]).href);
const state=Object.freeze([Object.freeze({id:'a',count:1}),Object.freeze({id:'b',count:2})]);
const ops=Object.freeze([Object.freeze({type:'put',id:'a',count:3}),Object.freeze({type:'remove',id:'a'}),Object.freeze({type:'put',id:'a',count:4}),Object.freeze({type:'put',id:'__proto__',count:0}),Object.freeze({type:'remove',id:'missing'})]);
assert.deepEqual(f(state,ops),[{id:'b',count:2},{id:'a',count:4},{id:'__proto__',count:0}]);
const result=f(state,[]);assert.notEqual(result,state);assert.notEqual(result[0],state[0]);result[0].count=9;assert.equal(state[0].count,1);
assert.deepEqual(f([{id:'constructor',count:1}],[{type:'put',id:'constructor',count:Number.MAX_SAFE_INTEGER}]),[{id:'constructor',count:Number.MAX_SAFE_INTEGER}]);
for(const op of [null,[],{},new Date(),{type:'put',id:'a',count:true},{type:'put',id:'a',count:'2'},{type:'put',id:'a',count:NaN},{type:'put',id:'a',count:2**53},{type:'put',id:'',count:2},{type:'put',id:'a',count:-1},{type:'remove',id:'a',count:1},{type:'put',id:'a',count:1,extra:1}]){
 const s=[{id:'a',count:1}];assert.throws(()=>f(s,[{type:'put',id:'a',count:7},op]),TypeError);assert.deepEqual(s,[{id:'a',count:1}]);
}
for(const bad of [null,{},'x',4])assert.throws(()=>f([],bad),TypeError);
''')}

def evaluate(name,path):
    f=FIXTURES[name]
    cmd=[sys.executable,'-c',f['checks'],str(Path(path).resolve())] if f['file'].endswith('.py') else ['node','--experimental-strip-types','--input-type=module','-e',f['checks'],str(Path(path).resolve())]
    try:
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
        return {'mandatory_pass':r.returncode==0,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'evaluator_version':hashlib.sha256(f['checks'].encode()).hexdigest()}
    except subprocess.TimeoutExpired:return {'mandatory_pass':False,'returncode':None,'stdout':'','stderr':'evaluation timeout','evaluator_version':hashlib.sha256(f['checks'].encode()).hexdigest()}

def validate():
    results={}
    for name,f in FIXTURES.items():
        with tempfile.TemporaryDirectory(prefix='jev-reference-') as d:
            p=Path(d)/f['file'];p.write_text(f['reference']);good=evaluate(name,p)
            p.write_text(f['starter']);bad=evaluate(name,p)
            if not good['mandatory_pass'] or bad['mandatory_pass']:raise AssertionError((name,good,bad))
            results[name]={'reference':good,'defective':bad,'starter_sha256':hashlib.sha256(f['starter'].encode()).hexdigest(),'contract_sha256':hashlib.sha256(f['contract'].encode()).hexdigest()}
    return results

if __name__=='__main__':print(json.dumps(validate(),indent=2))
