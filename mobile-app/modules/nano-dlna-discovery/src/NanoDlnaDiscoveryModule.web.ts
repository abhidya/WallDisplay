import { NativeModule, registerWebModule } from 'expo';

import type { DiscoveryResponse } from './NanoDlnaDiscovery.types';

class NanoDlnaDiscoveryModule extends NativeModule {
  async discoverAsync(serviceTypes: string[]): Promise<DiscoveryResponse> {
    return {
      services: [],
      startedAt: new Date().toISOString(),
      finishedAt: new Date().toISOString(),
      notes: [
        `Native discovery is unavailable on web. Requested service types: ${serviceTypes.join(', ')}`,
      ],
    };
  }
}

export default registerWebModule(NanoDlnaDiscoveryModule, 'NanoDlnaDiscovery');
