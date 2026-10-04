// A very small HTTP/1.1 server on 127.0.0.1, for this phone only.
// One request per connection (Connection: close). Enough for the simulator page.
import Foundation
import Network

struct HTTPRequest {
    let method: String
    let path: String          // without the query
    let query: [String: String]
    let headers: [String: String]   // lower-case names
    let body: Data
}

/// What a handler writes back. A plain reply, or a stream of chunks.
final class HTTPResponder: @unchecked Sendable {
    private let conn: NWConnection
    private var started = false
    private var extraHeaders: [String: String] = [:]
    /// True once the browser has gone away. A streaming handler checks this to stop early.
    private(set) var closed = false

    init(_ conn: NWConnection, extraHeaders: [String: String]) {
        self.conn = conn
        self.extraHeaders = extraHeaders
        conn.stateUpdateHandler = { [weak self] st in
            switch st {
            case .failed, .cancelled: self?.closed = true
            default: break
            }
        }
    }

    private func head(_ status: Int, _ type: String, length: Int?) -> Data {
        var h = "HTTP/1.1 \(status) \(Self.reason(status))\r\nContent-Type: \(type)\r\n"
        h += length.map { "Content-Length: \($0)\r\n" } ?? "Transfer-Encoding: chunked\r\n"
        h += "Cache-Control: no-store\r\nConnection: close\r\nX-Content-Type-Options: nosniff\r\n"
        for (k, v) in extraHeaders { h += "\(k): \(v)\r\n" }
        return Data((h + "\r\n").utf8)
    }

    func send(_ status: Int, _ type: String, _ body: Data) {
        guard !started else { return }
        started = true
        var d = head(status, type, length: body.count)
        d.append(body)
        conn.send(content: d, completion: .contentProcessed { [conn] _ in conn.cancel() })
    }
    func send(_ status: Int, text: String) { send(status, "text/plain; charset=utf-8", Data(text.utf8)) }
    func send(json: Any, status: Int = 200) {
        let d = (try? JSONSerialization.data(withJSONObject: json)) ?? Data("{}".utf8)
        send(status, "application/json", d)
    }

    // Streaming, as Ollama does: one JSON object per line.
    func startStream(_ type: String = "application/x-ndjson") {
        guard !started else { return }
        started = true
        conn.send(content: head(200, type, length: nil), completion: .contentProcessed { _ in })
    }
    func chunk(_ data: Data) {
        guard !closed, !data.isEmpty else { return }
        var d = Data(String(data.count, radix: 16).utf8)
        d.append(Data("\r\n".utf8)); d.append(data); d.append(Data("\r\n".utf8))
        conn.send(content: d, completion: .contentProcessed { [weak self] err in if err != nil { self?.closed = true } })
    }
    func line(_ obj: Any) {
        guard var d = try? JSONSerialization.data(withJSONObject: obj) else { return }
        d.append(0x0A)
        chunk(d)
    }
    func endStream() {
        conn.send(content: Data("0\r\n\r\n".utf8), completion: .contentProcessed { [conn] _ in conn.cancel() })
    }

    static func reason(_ s: Int) -> String {
        switch s {
        case 200: return "OK"; case 204: return "No Content"; case 400: return "Bad Request"
        case 403: return "Forbidden"; case 404: return "Not Found"; case 405: return "Method Not Allowed"
        default: return "Error"
        }
    }
}

final class HTTPServer: @unchecked Sendable {
    typealias Handler = (HTTPRequest, HTTPResponder) -> Void
    private let listener: NWListener
    private let queue: DispatchQueue
    private let handler: Handler
    private let headersFor: (HTTPRequest) -> [String: String]
    let port: UInt16

    /// Listens on 127.0.0.1 only. Other devices on the network cannot reach it.
    init(port: UInt16, name: String, headers: @escaping (HTTPRequest) -> [String: String] = { _ in [:] },
         handler: @escaping Handler) throws {
        let params = NWParameters.tcp
        params.requiredLocalEndpoint = .hostPort(host: "127.0.0.1", port: NWEndpoint.Port(rawValue: port)!)
        params.allowLocalEndpointReuse = true
        listener = try NWListener(using: params)
        queue = DispatchQueue(label: "http." + name, attributes: .concurrent)
        self.handler = handler
        self.headersFor = headers
        self.port = port
    }

    func start(ready: ((Bool) -> Void)? = nil) {
        listener.stateUpdateHandler = { st in
            switch st {
            case .ready: ready?(true)
            case .failed(let e): Log.write("server on port \(self.port) failed: \(e)"); ready?(false)
            default: break
            }
        }
        listener.newConnectionHandler = { [weak self] c in self?.accept(c) }
        listener.start(queue: queue)
    }
    func stop() { listener.cancel() }

    private func accept(_ c: NWConnection) {
        c.start(queue: queue)
        receive(c, Data())
    }

    private func receive(_ c: NWConnection, _ soFar: Data) {
        c.receive(minimumIncompleteLength: 1, maximumLength: 1 << 20) { [weak self] data, _, done, err in
            guard let self else { return }
            var buf = soFar
            if let data { buf.append(data) }
            if err != nil { c.cancel(); return }
            if buf.count > 8 << 20 { c.cancel(); return }       // 8 MB is far more than any question
            if let req = Self.parse(buf) {
                let r = HTTPResponder(c, extraHeaders: self.headersFor(req))
                self.handler(req, r)
            } else if done {
                c.cancel()
            } else {
                self.receive(c, buf)
            }
        }
    }

    /// Returns the request once the head and the whole body have arrived.
    static func parse(_ buf: Data) -> HTTPRequest? {
        guard let sep = buf.range(of: Data("\r\n\r\n".utf8)) else { return nil }
        guard let headText = String(data: buf[..<sep.lowerBound], encoding: .utf8) else { return nil }
        var lines = headText.components(separatedBy: "\r\n")
        let first = lines.removeFirst().split(separator: " ")
        guard first.count >= 2 else { return nil }
        var headers: [String: String] = [:]
        for l in lines {
            guard let i = l.firstIndex(of: ":") else { continue }
            headers[l[..<i].lowercased().trimmingCharacters(in: .whitespaces)] =
                l[l.index(after: i)...].trimmingCharacters(in: .whitespaces)
        }
        let len = Int(headers["content-length"] ?? "0") ?? 0
        let bodyStart = sep.upperBound
        guard buf.count - bodyStart >= len else { return nil }
        let target = String(first[1])
        let comps = URLComponents(string: "http://x" + target)
        var q: [String: String] = [:]
        for item in comps?.queryItems ?? [] { q[item.name] = item.value ?? "" }
        return HTTPRequest(method: String(first[0]), path: comps?.percentEncodedPath.removingPercentEncoding ?? "/",
                           query: q, headers: headers, body: buf.subdata(in: bodyStart..<(bodyStart + len)))
    }
}
