# Serves the built index.html with the web server that comes with Erlang, so the preview needs no Python or Node.
#
#     elixir build/serve.exs [port, default 8000]
#
# Run elixir build/build.exs first, and again after each change in build/.

port = System.argv() |> List.first("8000") |> String.to_integer()
root = Path.expand("..", __DIR__)

:ok = :inets.start()

{:ok, _pid} =
  :inets.start(:httpd,
    port: port,
    bind_address: {127, 0, 0, 1},
    server_name: ~c"localhost",
    server_root: String.to_charlist(System.tmp_dir!()),
    document_root: String.to_charlist(root),
    directory_index: [~c"index.html"],
    mime_types: [{~c"html", ~c"text/html; charset=utf-8"}]
  )

IO.puts("Serving #{root} at http://127.0.0.1:#{port}/. Press Ctrl+C twice to stop.")
Process.sleep(:infinity)
