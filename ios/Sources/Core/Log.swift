// The app's log: what it did, when, and how much memory it used at each step.
// On the phone it is log.txt in the app's folder (Files > On My iPhone > Patient), and the
// page's problem report includes its last lines (GET /log).
import Foundation
#if os(iOS)
import os
#endif

enum Log {
    private static let queue = DispatchQueue(label: "log")
    static let url: URL = {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent(ProcessInfo.processInfo.environment["VSP_LOG"] ?? "log.txt")
    }()

    /// The memory this app uses now, and (on a phone) how much more iOS allows before it closes the app.
    static func memory() -> String {
        var info = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<natural_t>.size)
        let kr = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count)
            }
        }
        let used = kr == KERN_SUCCESS ? Int(info.phys_footprint) / 1_048_576 : -1
        #if os(iOS)
        let left = Int(os_proc_available_memory()) / 1_048_576
        return "memory used \(used) MB, \(left) MB more allowed"
        #else
        return "memory used \(used) MB"
        #endif
    }

    static func write(_ msg: String, memory withMemory: Bool = false) {
        let line = ISO8601DateFormatter().string(from: Date()) + "  " + msg
            + (withMemory ? "  [" + memory() + "]" : "") + "\n"
        queue.async {
            FileHandle.standardError.write(Data(line.utf8))
            if let h = try? FileHandle(forWritingTo: url) {
                h.seekToEndOfFile(); h.write(Data(line.utf8)); try? h.close()
            } else {
                try? Data(line.utf8).write(to: url)
            }
        }
    }

    static func tail(_ bytes: Int = 6000) -> String {
        queue.sync {
            guard let d = try? Data(contentsOf: url) else { return "" }
            return String(decoding: d.suffix(bytes), as: UTF8.self)
        }
    }
}
