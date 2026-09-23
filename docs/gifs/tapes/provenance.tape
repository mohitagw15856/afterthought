Output docs/gifs/provenance.gif
Source docs/gifs/tapes/_common.tape
Type "grep 'lawyer' demo-vault/entities/people/siyu.md"
Enter
Sleep 2500ms
Type "# the block id ^at-llm-398c94ce04f9 resolves through the frontmatter to a message"
Enter
Sleep 1500ms
Type "grep -B3 -A3 'span: 398c94ce04f9' demo-vault/entities/people/siyu.md"
Enter
Sleep 5000ms
