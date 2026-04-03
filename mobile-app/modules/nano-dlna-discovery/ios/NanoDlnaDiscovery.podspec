Pod::Spec.new do |s|
  s.name           = 'NanoDlnaDiscovery'
  s.version        = '1.0.0'
  s.summary        = 'Native Bonjour discovery helpers for the nano-dlna mobile app'
  s.description    = 'Provides local-network service discovery for Cast/AirPlay style Bonjour services inside the Expo mobile app.'
  s.author         = 'nano-dlna'
  s.homepage       = 'https://docs.expo.dev/modules/'
  s.platforms      = {
    :ios => '15.1',
    :tvos => '15.1'
  }
  s.source         = { git: '' }
  s.static_framework = true

  s.dependency 'ExpoModulesCore'

  s.pod_target_xcconfig = {
    'DEFINES_MODULE' => 'YES',
  }

  s.source_files = "**/*.{h,m,mm,swift,hpp,cpp}"
end
