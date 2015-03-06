import asyncio
import json
from aiohttp.web import Application, Response
from aiohttp_sse import EventSourceResponse


@asyncio.coroutine
def hello(request):
    resp = EventSourceResponse()
    resp.start(request)
    for i in range(0, 100):
        print('foo')
        yield from asyncio.sleep(1, loop=loop)
        resp.send('foo {}'.format(i))

@asyncio.coroutine
def index(request):
    d = b"""
        <html>
        <head>
            <script type="text/javascript" src="http://code.jquery.com/jquery.min.js"></script>
            <script type="text/javascript">
            var evtSource = new EventSource("/hello");
            evtSource.onmessage = function(e) {
             $('#response').html(e.data);
            }

            </script>
        </head>
        <body>
            <h1>Response from server:</h1>
            <div id="response"></div>
        </body>
    </html>
    """
    resp = Response(body=d)

    return resp

def chat(request):
    d = b"""
    <html>
      <head>
        <title>Tiny Chat</title>
        <script src="//ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js"></script>
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
    for fut, es in app['sockets']:
        es.send(json.dumps(dict(data)), id=7)
    return Response()


@asyncio.coroutine
def subscribe(request):
    resp = EventSourceResponse()
    resp.start(request)

    fut = asyncio.Future(loop=loop)
    print('Someone joined.')
    for fut, es in request.app['sockets']:
        try:
            es.send('{"sender": "BOT", "message": "someone joined."}', id=5)
        except Exception as e:
            print(e)
            fut.set_result(None)
    request.app['sockets'].append((fut, resp))
    yield from fut
    return resp


@asyncio.coroutine
def init(loop):
    app = Application(loop=loop)
    app['sockets'] = []


    app.router.add_route('GET', '/hello', hello)
    app.router.add_route('GET', '/index', index)
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
