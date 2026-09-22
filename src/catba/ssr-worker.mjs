// ssr-worker.mjs - persistent Node SSR worker.
//
// Loads the Vite-built SSR bundle and renders React pages on request.
// Protocol: newline-delimited JSON on stdin/stdout.
//
//   Request:  {"id": 1, "page": "/", "props": {...}}
//   Response: {"id": 1, "html": "..."}
//   Error:    {"id": 1, "error": "..."}
//   Ready:    {"ready": true}
//
// Python owns this process. It starts, sends requests, and terminates it.

import { createInterface } from "readline"
import { pathToFileURL } from "url"

const bundlePath = process.argv[2]
if (!bundlePath) {
    process.stderr.write("ssr-worker: missing bundle path argument\n")
    process.exit(1)
}

let render
try {
    const bundleUrl = pathToFileURL(bundlePath).href
    const mod = await import(bundleUrl)
    render = mod.render
    if (typeof render !== "function") {
        throw new Error("SSR bundle does not export a render function")
    }
} catch (e) {
    process.stderr.write("ssr-worker: cannot load SSR bundle: " + e.message + "\n")
    process.exit(1)
}

// Signal readiness.
process.stdout.write(JSON.stringify({ ready: true }) + "\n")

const rl = createInterface({ input: process.stdin })

rl.on("line", (line) => {
    let req
    try {
        req = JSON.parse(line)
    } catch (e) {
        process.stdout.write(JSON.stringify({ id: null, error: "invalid JSON: " + e.message }) + "\n")
        return
    }

    try {
        const html = render(req.page, req.props)
        process.stdout.write(JSON.stringify({ id: req.id, html }) + "\n")
    } catch (e) {
        process.stdout.write(JSON.stringify({ id: req.id, error: e.message }) + "\n")
    }
})

rl.on("close", () => {
    process.exit(0)
})
