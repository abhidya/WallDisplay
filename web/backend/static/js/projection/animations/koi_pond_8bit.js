// Koi Pond 8-bit Animation - source-faithful local GIF playback
class KoiPond8BitAnimation extends BaseAnimation {
    setup() {
        this.backgroundMode = 'black';
        this.gifUrl = '/backend-static/assets/animations/koi_pond_8bit_source.gif';
        this.gifReady = false;
        this.frameCanvas = document.createElement('canvas');
        this.frameCanvas.width = this.canvas.width;
        this.frameCanvas.height = this.canvas.height;

        if (typeof window !== 'undefined' && typeof window.gifler === 'function') {
            window.gifler(this.gifUrl).animate(this.frameCanvas);
            this.gifReady = true;
        } else {
            console.warn('gifler is unavailable; koi_pond_8bit will not animate');
        }
    }

    drawCoverImage(image) {
        const canvasRatio = this.canvas.width / this.canvas.height;
        const imageRatio = image.width / image.height;

        let drawWidth = this.canvas.width;
        let drawHeight = this.canvas.height;
        let drawX = 0;
        let drawY = 0;

        if (imageRatio > canvasRatio) {
            drawHeight = this.canvas.height;
            drawWidth = drawHeight * imageRatio;
            drawX = (this.canvas.width - drawWidth) / 2;
        } else {
            drawWidth = this.canvas.width;
            drawHeight = drawWidth / imageRatio;
            drawY = (this.canvas.height - drawHeight) / 2;
        }

        this.ctx.drawImage(image, drawX, drawY, drawWidth, drawHeight);
    }

    draw() {
        if (this.backgroundMode === 'black') {
            this.ctx.fillStyle = '#000000';
            this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        } else {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }

        if (!this.gifReady) {
            return;
        }

        this.drawCoverImage(this.frameCanvas);
    }
}

if (typeof window !== 'undefined') {
    window.KoiPond8BitAnimation = KoiPond8BitAnimation;
}
