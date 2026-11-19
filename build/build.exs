# Builds index.html from build/atlas.src.html.
#
#     elixir build/build.exs
#
# Steps: compile build/app.css with the Tailwind CLI (daisyUI comes from build/vendor), then put the CSS and build/data.js into the page.
# On the first run the script downloads the pinned Tailwind CLI to build/bin with curl and checks its SHA-256.
# build/data.js comes from a private export script that lives with the private dataset, outside this repo.

defmodule Build do
  @tailwind "v4.3.4"
  @sha256 %{
    "macos-arm64" => "a516a11b439bfbb5ecd4a2d13b75e6cdcc284dc710aed8731e31d2e5c03895a4",
    "linux-x64" => "149a8ece5b855587a9c10de6da9dcbcfad0e47c4ed5dca219f721b3eae39d817"
  }

  def run(here) do
    css = compile_css(here)
    page = File.read!(Path.join(here, "atlas.src.html"))
    data = File.read!(Path.join(here, "data.js"))

    page =
      Enum.reduce([{"/*__CSS__*/", String.trim(css)}, {"/*__DATA__*/", data}], page, fn {marker, value}, page ->
        case String.split(page, marker) do
          [before, rest] -> before <> value <> rest
          parts -> raise "#{marker} must occur once in atlas.src.html, found #{length(parts) - 1}"
        end
      end)

    File.write!(Path.join(here, "../index.html"), page)
    IO.puts("index.html: #{div(byte_size(page), 1024)} KB, CSS #{div(byte_size(css), 1024)} KB")
  end

  defp compile_css(here) do
    out = Path.join(System.tmp_dir!(), "elixir-land-#{System.unique_integer([:positive])}.css")

    case System.cmd(tailwind(here), ["--input", "app.css", "--output", out, "--minify"], cd: here, stderr_to_stdout: true) do
      {_, 0} ->
        css = File.read!(out)
        File.rm!(out)
        css

      {log, status} ->
        raise "Tailwind exited with status #{status}:\n#{log}"
    end
  end

  defp tailwind(here) do
    target = target()
    binary = Path.join([here, "bin", "tailwindcss-#{@tailwind}-#{target}"])

    unless File.exists?(binary) do
      url = "https://github.com/tailwindlabs/tailwindcss/releases/download/#{@tailwind}/tailwindcss-#{target}"
      download = binary <> ".download"
      File.mkdir_p!(Path.dirname(binary))
      {_, 0} = System.cmd("curl", ["-fsSL", "-o", download, url])
      digest = :sha256 |> :crypto.hash(File.read!(download)) |> Base.encode16(case: :lower)

      if digest != Map.fetch!(@sha256, target) do
        File.rm!(download)
        raise "Checksum mismatch for #{url}: #{digest}"
      end

      File.chmod!(download, 0o755)
      File.rename!(download, binary)
    end

    binary
  end

  # Tailwind release names, from :os.type/0 and the CPU part of the system architecture, such as "aarch64-apple-darwin".
  @os %{darwin: "macos", linux: "linux"}
  @arch %{"aarch64" => "arm64", "arm64" => "arm64", "x86_64" => "x64", "amd64" => "x64"}

  defp target do
    {:unix, os} = :os.type()
    [cpu | _] = :erlang.system_info(:system_architecture) |> to_string() |> String.split("-")
    "#{Map.fetch!(@os, os)}-#{Map.fetch!(@arch, cpu)}"
  end
end

Build.run(__DIR__)
