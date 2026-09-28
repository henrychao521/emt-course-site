import json,sys
sys.path.insert(0,'tools/quizgen')
from validate import extract_json
def show(items, prefix):
    for i,q in enumerate(items,1):
        print(f"[{prefix}{i:02d}] {q['type']} d{q['difficulty']} {q['chapter']} kp={q['kp']} src={q['sources']}")
        print("  Q:", q['stem'])
        if q['type']=='order': print("  ORDER:", " → ".join(q['items']))
        else:
            for o in q['options']: print("   ", "*" if o==q['answer'] else "-", o)
        print("  E:", q['explain'])
if __name__=="__main__":
    f=sys.argv[1]; t=open(f).read()
    show(extract_json(t), sys.argv[2])
