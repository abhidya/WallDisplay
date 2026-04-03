const IMPORTED_SHADERTOY_ANIMATIONS = [
    { id: 'star_psf', shaderId: 'XdsGWs', className: 'ImportedShadertoyXdsGWsAnimation', base: 'single' },
    { id: 'alien_tech', shaderId: 'XtX3zj', className: 'ImportedShadertoyXtX3zjAnimation', base: 'single' },
    { id: 'maze_automata', shaderId: 'lsccDB', className: 'ImportedShadertoyLsccDBAnimation', base: 'multi' },
    { id: 'outer_space_planet', shaderId: '4llBD8', className: 'ImportedShadertoy4llBD8Animation', base: 'multi' },
    { id: 'alien_tunnel', shaderId: 'X3ySRc', className: 'ImportedShadertoyX3ySRcAnimation', base: 'multi' },
    { id: 'alien_waterworld', shaderId: 'WtXyW4', className: 'ImportedShadertoyWtXyW4Animation', base: 'single' },
    { id: 'alien_space_jockey', shaderId: 'mdB3Rh', className: 'ImportedShadertoyMdB3RhAnimation', base: 'single' },
    { id: 'alien_core', shaderId: '4tcXRr', className: 'ImportedShadertoy4tcXRrAnimation', base: 'single' },
    { id: 'volcanic', shaderId: 'XsX3RB', className: 'ImportedShadertoyXsX3RBAnimation', base: 'multi' },
    { id: 'kepler_256o', shaderId: 'XsjGRd', className: 'ImportedShadertoyXsjGRdAnimation', base: 'single' },
    { id: 'night_skyline_buffered', shaderId: 'ws2yRh', className: 'ImportedShadertoyWs2yRhAnimation', base: 'multi' },
    { id: 'vaporwave_0001', shaderId: 'wtSXD1', className: 'ImportedShadertoyWtSXD1Animation', base: 'single' },
    { id: 'anime_background_3', shaderId: 'fsGXW1', className: 'ImportedShadertoyFsGXW1Animation', base: 'multi' },
    { id: 'grid_and_lines', shaderId: 'lcBcDw', className: 'ImportedShadertoyLcBcDwAnimation', base: 'single' },
    { id: 'anime_background', shaderId: 'fdyXzz', className: 'ImportedShadertoyFdyXzzAnimation', base: 'multi' },
    { id: 'unstable_universe', shaderId: 'wtlfz8', className: 'ImportedShadertoyWtlfz8Animation', base: 'multi' },
    { id: 'lensing', shaderId: 'MtByRh', className: 'ImportedShadertoyMtByRhAnimation', base: 'single' },
    { id: 'kerr_newman_black_hole', shaderId: 'wXdfzj', className: 'ImportedShadertoyWXdfzjAnimation', base: 'multi' },
    { id: 'descent_3d', shaderId: 'wdfGW4', className: 'ImportedShadertoyWdfGW4Animation', base: 'single' },
    { id: 'singularity_381', shaderId: '3csSWB', className: 'ImportedShadertoy3csSWBAnimation', base: 'single' },
    { id: 'gargantua_hdr_bloom', shaderId: 'lstSRS', className: 'ImportedShadertoyLstSRSAnimation', base: 'multi' },
    { id: 'mandelbrot_orbit_traps', shaderId: 'ldf3DN', className: 'ImportedShadertoyLdf3DNAnimation', base: 'single' },
    { id: 'steel_lattice', shaderId: '4tlSWl', className: 'ImportedShadertoy4tlSWlAnimation', base: 'single' },
    { id: 'black_hole_accretion_disk', shaderId: 'tsBXW3', className: 'ImportedShadertoyTsBXW3Animation', base: 'single' },
    { id: 'simple_greeble_split4', shaderId: '4tXcRl', className: 'ImportedShadertoy4tXcRlAnimation', base: 'single' },
    { id: 'windows_95', shaderId: 'XstXR2', className: 'ImportedShadertoyXstXR2Animation', base: 'single' },
];

(function registerImportedShadertoyAnimations() {
    IMPORTED_SHADERTOY_ANIMATIONS.forEach((entry) => {
        const BaseClass = entry.base === 'multi'
            ? window.ShadertoyMultiPassAnimation
            : window.ShadertoySinglePassAnimation;

        if (!BaseClass) {
            return;
        }

        window[entry.className] = class extends BaseClass {
            getShaderAssetPath() {
                return `/backend-static/assets/shadertoy/${entry.shaderId}.json`;
            }
        };
    });

    window.ImportedShadertoyAnimationsManifest = IMPORTED_SHADERTOY_ANIMATIONS;
})();
