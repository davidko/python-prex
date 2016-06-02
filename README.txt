Python Remote Execution (PREX)

This is an experimental server that executes Python scripts (or any kind of
scripts, really) it receives over a websocket connection. The connection allows
a web client to launch and interact with Python programs in real-time. 

The main use-case scenario is to enable a client device running a web browser,
such as a smart phone or ChromeBook, to execute Python scripts in a natural
way.

Please do _NOT_ run the server on your personal computer! Allowing clients to
run Python scripts from web apps is highly insecure. You have been warned!
