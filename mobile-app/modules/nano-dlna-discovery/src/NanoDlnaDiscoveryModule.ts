import { requireNativeModule } from 'expo';

import type { DiscoveryResponse } from './NanoDlnaDiscovery.types';

declare class NanoDlnaDiscoveryModule {
  discoverAsync(serviceTypes: string[], timeoutMs?: number): Promise<DiscoveryResponse>;
}

export default requireNativeModule<NanoDlnaDiscoveryModule>('NanoDlnaDiscovery');
