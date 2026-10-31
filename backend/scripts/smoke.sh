#!/usr/bin/env bash
# Smoke test: pipeline on the fixture + API assertions. Run from backend/: bash scripts/smoke.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export DATA_DIR="${DATA_DIR:-$(pwd)/data/smoke}"
rm -rf "$DATA_DIR"; mkdir -p "$DATA_DIR"
PORT=8765
BASE="http://127.0.0.1:$PORT"

python3 -m uvicorn app.main:app --port $PORT --log-level warning &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for i in $(seq 1 40); do curl -sf "$BASE/api/health" >/dev/null && break; sleep 0.25; done
curl -sf "$BASE/api/health"; echo

echo "== create demo source"
SID=$(curl -sf -X POST "$BASE/api/sources" -H 'content-type: application/json' -d '{"demo":true}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
for i in $(seq 1 120); do
  ST=$(curl -sf "$BASE/api/sources/$SID" | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')
  [[ "$ST" == "ready" || "$ST" == "error" ]] && break; sleep 0.5
done
[[ "$ST" == "ready" ]] || { echo "source status: $ST"; curl -s "$BASE/api/sources/$SID"; exit 1; }
echo "source $SID ready"

echo "== transcript + moments assertions"
curl -sf "$BASE/api/sources/$SID/transcript" > "$DATA_DIR/t.json"
curl -sf "$BASE/api/sources/$SID/moments" > "$DATA_DIR/m.json"
python3 - "$DATA_DIR/t.json" "$DATA_DIR/m.json" <<'EOF'
import json, re, sys
t = json.load(open(sys.argv[1])); ms = json.load(open(sys.argv[2]))
utts = t["utterances"]
assert len(utts) > 0 and all(u["words"] for u in utts), "transcript must have utterances with words"
assert len(ms) >= 4, f"expected >= 4 moments, got {len(ms)}"
norm = lambda s: re.sub(r"\s+", " ", s).strip()
starts = {round(u["start"], 2) for u in utts}; ends = {round(u["end"], 2) for u in utts}
for m in ms:
    joined = norm(" ".join(u["text"] for u in utts if m["start_utt"] <= u["id"] <= m["end_utt"]))
    assert norm(m["quote"]) in joined, f"quote not verbatim: {m['quote']!r}"
    assert round(m["start"], 2) in starts and round(m["end"], 2) in ends, f"span not on utterance boundaries: {m['id']}"
    assert 0 <= m["integrity"]["score"] <= 100
    for f in m["integrity"]["flags"]:
        assert f["evidence"] and isinstance(f["at"], (int, float)), "flag needs evidence + timestamp"
    assert 12 - 0.01 <= m["end"] - m["start"] <= 75 + 0.01, f"duration out of range: {m['id']}"
print(f"ok: {len(utts)} utterances, {len(ms)} moments, scores {[m['integrity']['score'] for m in ms]}")
EOF

MID=$(python3 -c 'import json,sys;ms=json.load(open(sys.argv[1]));print(ms[0]["id"])' "$DATA_DIR/m.json")

echo "== render before approval must 409"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/moments/$MID/render")
[[ "$CODE" == "409" ]] || { echo "expected 409, got $CODE"; exit 1; }
echo "409 ok"

echo "== extend to include (PATCH) re-scores"
SUG=$(python3 -c 'import json,sys;ms=json.load(open(sys.argv[1]));m=[m for m in ms if m["integrity"].get("suggested_start") is not None];print(m[0]["id"] if m else "")' "$DATA_DIR/m.json")
if [[ -n "$SUG" ]]; then
  BEFORE=$(curl -sf "$BASE/api/moments/$SUG" | python3 -c 'import sys,json;m=json.load(sys.stdin);print(m["integrity"]["score"], m["integrity"]["suggested_start"])')
  S=$(echo "$BEFORE" | cut -d' ' -f2)
  AFTER=$(curl -sf -X PATCH "$BASE/api/moments/$SUG" -H 'content-type: application/json' -d "{\"start\": $S, \"by\": \"smoke\"}" | python3 -c 'import sys,json;m=json.load(sys.stdin);print(m["integrity"]["score"], len(m["adjustments"]))')
  echo "score before/after extend: $BEFORE → $AFTER"
  MID=$SUG
fi

echo "== approve → render → manifest"
CID=$(curl -sf -X POST "$BASE/api/moments/$MID/approve" -H 'content-type: application/json' -d '{"by":"smoke@test"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["clip_id"])')
for i in $(seq 1 240); do
  CST=$(curl -sf "$BASE/api/clips/$CID" | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')
  [[ "$CST" == "ready" || "$CST" == "error" ]] && break; sleep 0.5
done
[[ "$CST" == "ready" ]] || { echo "clip status: $CST"; curl -s "$BASE/api/clips/$CID"; exit 1; }
curl -sf "$BASE/api/clips/$CID/manifest" > "$DATA_DIR/manifest.json"
python3 - "$DATA_DIR/manifest.json" "$DATA_DIR" <<'EOF'
import hashlib, json, sys
man = json.load(open(sys.argv[1]))
clip = f"{sys.argv[2]}/clips/{man['clip_id']}/clip.mp4"
h = hashlib.sha256(open(clip, "rb").read()).hexdigest()
assert man["render"]["sha256"] == h, "manifest sha256 must match clip file"
assert man["source"]["sha256"] and man["approval"]["by"] == "smoke@test"
print("manifest ok; clip sha256", h[:16])
EOF
curl -sf "$BASE/v/$CID" | grep -q "Recorte" && echo "verify page ok"

echo "== chat"
curl -sf -X POST "$BASE/api/sources/$SID/chat" -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"Encontrá cada vez que menciona la inflación"}]}' | python3 -c 'import sys,json;r=json.load(sys.stdin);assert "[" in r["reply"], r;print("chat ok:", r["reply"][:120].replace("\n"," "), "| created", len(r["created_moment_ids"]))'

echo "SMOKE PASSED"
