import asyncio
import json
from aiohttp.web import Application, Response
from aiohttp_sse import EventSourceResponse


def chat(request):
    d = b"""
    <html>
      <head>
        <title>Tiny Chat</title>
        <script
        src="//ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js">
        </script>
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
          $(function(){
            var source = new EventSource("/subscribe");
            source.addEventListener('message', function(event) {
              console.log(event.data)
              message = JSON.parse(event.data);
              $('.messages').append(
              "<div class=sender>"+message.sender+"</div>"+
              "<div class=message>"+message.message+"</div>");
            });

            $('form').submit(function(e){
              e.preventDefault();
              $.post('/everyone',
                {
                  sender: $('.name').text(),
                  message: $('form .message').val()
                })
              $('form .message').val('')
            });

            $('.change-name').click(function(){
              name = prompt("Enter your name:");
              $('.name').text(name);
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
    resp = Response(body=d)

    return resp


@asyncio.coroutine
def message(request):
    app = request.app
    data = yield from request.post()

    for es in app['sockets']:
        payload = json.dumps(dict(data))
        es.send(payload)
    return Response()


@asyncio.coroutine
def subscribe(request):
    response = EventSourceResponse()
    response.start(request)
    app = request.app

    print('Someone joined.')
    request.app['sockets'].add(response)
    try:
        yield from response.wait()
    except Exception as e:
        app['sockets'].remove(response)
        raise e

    return response


@asyncio.coroutine
def init(loop):
    app = Application(loop=loop)
    app['sockets'] = set()

    app.router.add_route('GET', '/chat', chat)
    app.router.add_route('POST', '/everyone', message)
    app.router.add_route('GET', '/subscribe', subscribe)

    handler = app.make_handler()
    srv = yield from loop.create_server(handler, '127.0.0.1', 8080)
    print("Server started at http://127.0.0.1:8080")
    return srv, handler
loop = asyncio.get_event_loop()
srv, handler = loop.run_until_complete(init(loop))
try:
    loop.run_forever()
except KeyboardInterrupt:
    loop.run_until_complete(handler.finish_connections())
