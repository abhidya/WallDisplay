class SwarmingAnchovetaAnimation extends ShadertoyMultiPassAnimation {
    getShaderAssetPath() {
        return '/backend-static/assets/shadertoy/mtSGDt.json';
    }

    getExternalChannelDefinitions() {
        return {
            main: {
                src: '/backend-static/assets/shadertoy/media/mtSGDt_texture.png',
                filter: 'mipmap',
                wrap: 'repeat',
                vflip: true,
            },
        };
    }
}

window.SwarmingAnchovetaAnimation = SwarmingAnchovetaAnimation;
