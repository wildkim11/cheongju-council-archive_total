"""The immutable initial shards are fixtures, never the growing live index."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def initial_meetings():
 rows=[]
 for term in range(1,5):rows.extend(json.loads((ROOT/f'indexes/integrated/initial_term_{term}.json').read_text(encoding='utf-8')))
 return sorted(rows,key=lambda r:(r['date'],r['meeting_id']))
