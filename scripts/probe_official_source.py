"""Minimal live probe: one official generation-root request only."""
import json
from collect_integrated_minutes import _tree, SUPPORTED_TERMS

def main():
    roots=_tree("Gnrtn",{"var10":"SvcMntsTreeGnrtn"})
    available=sorted(
        int(x["var01"]) for x in roots
        if str(x.get("var01","")).isdigit()
    )
    missing=[x for x in SUPPORTED_TERMS if x not in available]
    result={"available_terms":available,"required_terms":list(SUPPORTED_TERMS),"missing":missing}
    print(json.dumps(result,ensure_ascii=False))
    if missing:
        raise SystemExit("Missing required integrated council terms: "+",".join(map(str,missing)))

if __name__=="__main__":
    main()
