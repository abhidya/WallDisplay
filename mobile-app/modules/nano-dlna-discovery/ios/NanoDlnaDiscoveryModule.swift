import ExpoModulesCore
import Foundation

public final class NanoDlnaDiscoveryModule: Module {
  public func definition() -> ModuleDefinition {
    Name("NanoDlnaDiscovery")

    AsyncFunction("discoverAsync") { (serviceTypes: [String], timeoutMs: Int?) -> [String: Any] in
      let session = BonjourDiscoverySession(serviceTypes: serviceTypes, timeoutMs: timeoutMs ?? 4000)
      return await session.run()
    }
  }
}

final class BonjourDiscoverySession: NSObject, NetServiceBrowserDelegate, NetServiceDelegate {
  private let startedAt = ISO8601DateFormatter().string(from: Date())
  private let timeoutMs: Int
  private let serviceTypes: [String]
  private let notesLock = NSLock()
  private let servicesLock = NSLock()
  private var browsers: [NetServiceBrowser] = []
  private var services: [String: [String: Any]] = [:]
  private var continuation: CheckedContinuation<[String: Any], Never>?
  private let formatter = ISO8601DateFormatter()

  init(serviceTypes: [String], timeoutMs: Int) {
    self.serviceTypes = serviceTypes
      .map { BonjourDiscoverySession.normalizeServiceType($0) }
      .filter { !$0.isEmpty }
    self.timeoutMs = timeoutMs
  }

  func run() async -> [String: Any] {
    if serviceTypes.isEmpty {
      return response(notes: ["No Bonjour service types were requested."])
    }

    return await withCheckedContinuation { continuation in
      self.continuation = continuation
      for serviceType in serviceTypes {
        let browser = NetServiceBrowser()
        browser.delegate = self
        browsers.append(browser)
        browser.searchForServices(ofType: serviceType, inDomain: "local.")
      }

      Task {
        try? await Task.sleep(nanoseconds: UInt64(timeoutMs) * 1_000_000)
        finishIfNeeded()
      }
    }
  }

  func netServiceBrowser(_ browser: NetServiceBrowser, didFind service: NetService, moreComing: Bool) {
    service.delegate = self
    store(service: service)
    service.resolve(withTimeout: 2.5)
  }

  func netServiceDidResolveAddress(_ sender: NetService) {
    store(service: sender)
  }

  func netService(_ sender: NetService, didNotResolve errorDict: [String : NSNumber]) {
    appendNote("Resolve failed for \(sender.name): \(errorDict)")
  }

  func netServiceBrowser(_ browser: NetServiceBrowser, didNotSearch errorDict: [String : NSNumber]) {
    appendNote("Bonjour search failed: \(errorDict)")
  }

  private func store(service: NetService) {
    servicesLock.lock()
    defer { servicesLock.unlock() }

    let id = "\(service.type)|\(service.name)"
    var payload: [String: Any] = [
      "id": id,
      "name": service.name,
      "serviceType": service.type,
      "domain": service.domain,
    ]

    if let hostName = service.hostName, !hostName.isEmpty {
      payload["hostName"] = hostName
    }

    if service.port > 0 {
      payload["port"] = service.port
    }

    services[id] = payload
  }

  private func appendNote(_ note: String) {
    notesLock.lock()
    defer { notesLock.unlock() }
    if collectedNotes.contains(note) { return }
    collectedNotes.append(note)
  }

  private var collectedNotes: [String] = []

  private func finishIfNeeded() {
    guard let continuation else { return }
    browsers.forEach { $0.stop() }
    self.continuation = nil
    continuation.resume(returning: response(notes: collectedNotes))
  }

  private func response(notes: [String]) -> [String: Any] {
    servicesLock.lock()
    let serviceList = Array(services.values)
    servicesLock.unlock()

    return [
      "services": serviceList,
      "startedAt": startedAt,
      "finishedAt": formatter.string(from: Date()),
      "notes": notes,
    ]
  }

  private static func normalizeServiceType(_ serviceType: String) -> String {
    let trimmed = serviceType.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty else { return trimmed }
    return trimmed.hasSuffix(".") ? trimmed : "\(trimmed)."
  }
}
