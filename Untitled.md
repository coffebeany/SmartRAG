curl --request POST \
  --url https://api.siliconflow.cn/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-pnhpkujcrppaznpdytjlbpdryeqroyvjnlrgqacaqbzbftiq" \
  -d '{
    "model": "Qwen/Qwen3.5-4B",
    "messages": [
      {"role": "system", "content": "你是一个有用的助手"}
    ]
  }'



PS C:\Users\yk> curl.exe --request POST "https://api.siliconflow.cn/v1/chat/completions" --header "Content-Type: application/json" --header "Authorization: Bearer sk-pnhpkujcrppaznpdytjlbpdryeqroyvjnlrgqacaqbzbftiq" --data '{"model":"Qwen/Qwen3.5-4B","messages":[{"role":"system","content":"你是一个有用的助手"}]}'
"Invalid token"







curl.exe --request POST "https://api.siliconflow.cn/v1/chat/completions" --header "Content-Type: application/json" --header "Authorization: Bearer sk-pnhpkujcrppaznpdytjlbpdryeqroyvjnlrgqacaqbzbftiq" --data '{"model":"Qwen/Qwen3.5-4B","messages":[{"role":"system","content":"你是一个有用的助手"},{"role":"user","content":"你好，请介绍一下你自己"}]}'

sk-pnhpkujcrppaznpdytjlbpdryeqroyvjnlrgqacaqbzbftiq



curl.exe "https://api.siliconflow.cn/v1/models" `
  --header "Authorization: Bearer sk-pnhpkujcrppaznpdytjlbp



deepseek-ai/DeepSeek-V4-Flash



curl.exe --request POST "https://api.siliconflow.cn/v1/chat/completions" `
  --header "Content-Type: application/json" `
  --header "Authorization: Bearer sk-pnhpkujcrppaznpdytjlbpdryeqroyvjnlrgqacaqbzbftiq" `
  --data '{"model":"deepseek-ai/DeepSeek-V4-Flash","messages":[{"role":"user","content":"你好，请介绍一下你自己"}]}'

