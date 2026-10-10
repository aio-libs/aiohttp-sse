import asyncio
import json

from aiohttp import web

from aiohttp_sse import EventSourceResponse, sse_response

channels = web.AppKey("channels", set[asyncio.Queue[str]])


async def chat(_request: web.Request) -> web.Response:
    html = """
    <html>
      <head>
        <title>Tiny Chat</title>
        <style>
        .messages {
          overflow: scroll;
          height: 200px;
        }
        .messages .sender{
          float: left;
          clear: left;
          width: 120px;
          margin-right: 10px;
          text-align: right;
          background-color: #ddd;
        }
        .messages .message{
          float: left;
        }
        form {
          display: inline;
        }

        </style>
        <script>
          document.addEventListener("DOMContentLoaded", () => {
            const messages = document.querySelector(".messages");
            const nameEl = document.querySelector(".name");
            const form = document.querySelector("form");
            const input = form.querySelector(".message");

            const source = new EventSource("/subscribe");
            source.addEventListener("message", (event) => {
              console.log(event.data);
              const message = JSON.parse(event.data);
              const sender = document.createElement("div");
              sender.className = "sender";
              sender.textContent = message.sender;
              const text = document.createElement("div");
              text.className = "message";
              text.textContent = message.message;
              messages.append(sender, text);
            });

            form.addEventListener("submit", (e) => {
              e.preventDefault();
              fetch("/everyone", {
                method: "POST",
                body: new URLSearchParams({
                  sender: nameEl.textContent,
                  message: input.value,
                }),
              });
              input.value = "";
            });

            document.querySelector(".change-name").addEventListener("click", () => {
              const name = prompt("Enter your name:");
              if (name !== null) nameEl.textContent = name;
            });
          });
        </script>
      </head>
      <body>
        <div class=messages></div>
        <button class=change-name>Change Name</button>
        <span class=name>Anonymous</span>
        <span>:</span>
      <form>
        <input class="message" placeholder="Message..."/>
        <input type="submit" value="Send" />
      </form>
      </body>
    </html>

    """
    return web.Response(text=html, content_type="text/html")


async def message(request: web.Request) -> web.Response:
    app = request.app
    data = await request.post()

    for queue in app[channels]:
        payload = json.dumps(dict(data))
        await queue.put(payload)
    return web.Response()


async def subscribe(request: web.Request) -> EventSourceResponse:
    async with sse_response(request) as response:
        app = request.app
        queue: asyncio.Queue[str] = asyncio.Queue()
        print("Someone joined.")
        app[channels].add(queue)
        try:
            while response.is_connected():
                payload = await queue.get()
                await response.send(payload)
                queue.task_done()
        finally:
            app[channels].remove(queue)
            print("Someone left.")
    return response


if __name__ == "__main__":
    app = web.Application()
    app[channels] = set()

    app.router.add_route("GET", "/", chat)
    app.router.add_route("POST", "/everyone", message)
    app.router.add_route("GET", "/subscribe", subscribe)
    web.run_app(app, host="127.0.0.1", port=8080)
