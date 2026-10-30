# MCP Tool Allowlisting Example App

Come up with a FastAPI web application that uses Jinja2 templates to render a simple UI. Use something like Tailwind CSS for the frontend.

The application needs to have two routes:
1. An insecure route (the default / route)
2. A secure route


Once the user starts the application, they should be routed to the default route. In the default route, it needs to open up a page that has a large text area that provides a place for a user to type in a prompt and submit it.

You need to have the same thing for the insecure route, except that change of the color combinations to be a lot more oriented towards security, something like green. 

Now, once the user submits it as a POST request, this should trigger an AI agent job in the background and come back with a response from that agent which is going to be a basic string response that needs to be printed on the screen just below the text area. You can ignore the AI agent implementation part of it and just build the front-end and HTTP request handling to the back-end. 

Use UV for the package manager and use the native UV operations like UV add instead of using pip. Do not use any sort of database for this, it is absolutely not necessary. Any other back-end or data source implementation is also not necessary. 