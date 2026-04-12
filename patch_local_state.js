const fs = require('fs');
const path = 'mobile-app/src/control-plane/localState.ts';
let code = fs.readFileSync(path, 'utf-8');

// 1. Update interface
code = code.replace(
  '  projectionSessions: ProjectionSessionSummary[];\n}',
  '  projectionSessions: ProjectionSessionSummary[];\n  structuredLightingSessions: JsonRecord[];\n  projectionAnimations: JsonRecord[];\n}'
);

// 2. Update createInitialState()
code = code.replace(
  '    projectionSessions: [],\n  };\n}',
  '    projectionSessions: [],\n    structuredLightingSessions: [],\n    projectionAnimations: [],\n  };\n}'
);

// 3. Update ensureStateShape()
code = code.replace(
  '      ? state.deferredFeatures\n      : createInitialState().deferredFeatures,\n  };\n}',
  '      ? state.deferredFeatures\n      : createInitialState().deferredFeatures,\n    structuredLightingSessions: state.structuredLightingSessions?.length ? state.structuredLightingSessions : createInitialState().structuredLightingSessions,\n    projectionAnimations: state.projectionAnimations?.length ? state.projectionAnimations : createInitialState().projectionAnimations,\n  };\n}'
);

fs.writeFileSync(path, code);
console.log('Patched localState.ts successfully');
