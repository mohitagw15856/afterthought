Output docs/gifs/compile.gif
Source docs/gifs/tapes/_common.tape
Type "afterthought compile examples/chatgpt-export/conversations.json --vault demo-vault --dry-run --fixtures examples/chatgpt-export/fixtures"
Sleep 800ms
Enter
Sleep 2500ms
Type "afterthought status --vault demo-vault"
Enter
Sleep 2000ms
Type "sed -n '/^# /,$p' demo-vault/entities/people/siyu.md"
Enter
Sleep 5000ms
