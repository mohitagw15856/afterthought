Output docs/gifs/idempotent.gif
Source docs/gifs/tapes/_common.tape
Type "afterthought compile examples/chatgpt-export/conversations.json --vault demo-vault --dry-run --fixtures examples/chatgpt-export/fixtures"
Enter
Sleep 2500ms
Type "afterthought compile examples/chatgpt-export/conversations.json --vault demo-vault --dry-run --fixtures examples/chatgpt-export/fixtures"
Enter
Sleep 4000ms
