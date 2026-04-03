package expo.modules.mymodule

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.util.concurrent.ConcurrentHashMap

class NanoDlnaDiscoveryModule : Module() {
  override fun definition() = ModuleDefinition {
    Name("NanoDlnaDiscovery")

    AsyncFunction("discoverAsync") { serviceTypes: List<String>, timeoutMs: Int? ->
      withContext(Dispatchers.IO) {
        discoverServices(serviceTypes, timeoutMs ?: 4000)
      }
    }
  }

  private suspend fun discoverServices(
    serviceTypes: List<String>,
    timeoutMs: Int,
  ): Map<String, Any> {
    val reactContext = appContext.reactContext ?: return emptyDiscoveryResponse(
      notes = listOf("React context unavailable; native discovery could not start."),
    )

    val nsdManager = reactContext.getSystemService(Context.NSD_SERVICE) as? NsdManager
      ?: return emptyDiscoveryResponse(
        notes = listOf("NsdManager unavailable on this device."),
      )

    val wifiManager = reactContext.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
    val multicastLock = wifiManager
      ?.createMulticastLock("nano-dlna-discovery")
      ?.apply {
        setReferenceCounted(false)
        try {
          acquire()
        } catch (_: Throwable) {
          // Best effort only. Discovery may still work on some devices without the lock.
        }
      }

    val startedAt = isoTimestamp()
    val notes = mutableListOf<String>()
    val resolvedServices = ConcurrentHashMap<String, MutableMap<String, Any>>()
    val listeners = mutableListOf<Pair<String, NsdManager.DiscoveryListener>>()

    fun record(serviceInfo: NsdServiceInfo) {
      val serviceType = serviceInfo.serviceType ?: return
      val serviceName = serviceInfo.serviceName ?: serviceType
      val id = "${serviceType}|${serviceName}"
      val payload = mutableMapOf<String, Any>(
        "id" to id,
        "name" to serviceName,
        "serviceType" to serviceType,
        "domain" to "local.",
      )
      serviceInfo.host?.hostAddress?.let { payload["hostName"] = it }
      val port = serviceInfo.port
      if (port > 0) {
        payload["port"] = port
      }
      resolvedServices[id] = payload
    }

    for (rawType in serviceTypes.distinct()) {
      val normalizedType = normalizeServiceType(rawType)
      val listener = object : NsdManager.DiscoveryListener {
        override fun onDiscoveryStarted(regType: String) = Unit

        override fun onServiceFound(serviceInfo: NsdServiceInfo) {
          record(serviceInfo)
          try {
            nsdManager.resolveService(
              serviceInfo,
              object : NsdManager.ResolveListener {
                override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                  notes.add("Resolve failed for ${serviceInfo.serviceName ?: normalizedType}: $errorCode")
                }

                override fun onServiceResolved(resolvedServiceInfo: NsdServiceInfo) {
                  record(resolvedServiceInfo)
                }
              },
            )
          } catch (error: Throwable) {
            notes.add("Resolve threw for ${serviceInfo.serviceName ?: normalizedType}: ${error.message}")
          }
        }

        override fun onServiceLost(serviceInfo: NsdServiceInfo) = Unit

        override fun onDiscoveryStopped(serviceType: String) = Unit

        override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
          notes.add("Discovery failed to start for $serviceType: $errorCode")
          try {
            nsdManager.stopServiceDiscovery(this)
          } catch (_: Throwable) {
          }
        }

        override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
          notes.add("Discovery failed to stop for $serviceType: $errorCode")
          try {
            nsdManager.stopServiceDiscovery(this)
          } catch (_: Throwable) {
          }
        }
      }

      listeners += normalizedType to listener
      try {
        nsdManager.discoverServices(normalizedType, NsdManager.PROTOCOL_DNS_SD, listener)
      } catch (error: Throwable) {
        notes.add("Unable to start discovery for $normalizedType: ${error.message}")
      }
    }

    delay(timeoutMs.toLong())

    listeners.forEach { (_, listener) ->
      try {
        nsdManager.stopServiceDiscovery(listener)
      } catch (_: Throwable) {
      }
    }

    try {
      multicastLock?.release()
    } catch (_: Throwable) {
    }

    return mapOf(
      "services" to resolvedServices.values.toList(),
      "startedAt" to startedAt,
      "finishedAt" to isoTimestamp(),
      "notes" to notes,
    )
  }

  private fun normalizeServiceType(serviceType: String): String {
    val trimmed = serviceType.trim()
    return if (trimmed.endsWith(".")) trimmed else "$trimmed."
  }

  private fun emptyDiscoveryResponse(notes: List<String>): Map<String, Any> = mapOf(
    "services" to emptyList<Map<String, Any>>(),
    "startedAt" to isoTimestamp(),
    "finishedAt" to isoTimestamp(),
    "notes" to notes,
  )

  private fun isoTimestamp(): String = java.time.Instant.now().toString()
}
