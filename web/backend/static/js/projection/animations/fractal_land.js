class FractalLandAnimation extends ShadertoySinglePassAnimation {
    getShaderAssetPath() {
        return '/backend-static/assets/shadertoy/XsBXWt.json';
    }

    getChannelDefinitions() {
        return [
            {
                channel: 0,
                kind: 'audio',
                width: 512,
                height: 2,
                filter: 'linear',
                wrap: 'clamp',
                seed: 1.37,
            },
            {
                channel: 1,
                kind: 'image',
                src: '/backend-static/assets/shadertoy/media/XsBXWt_nyan.png',
                filter: 'mipmap',
                wrap: 'repeat',
                vflip: true,
            },
        ];
    }
}

window.FractalLandAnimation = FractalLandAnimation;
