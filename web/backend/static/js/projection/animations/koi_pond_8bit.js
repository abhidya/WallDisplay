// Koi Pond 8-bit Animation - source-faithful local GIF host
class KoiPond8BitAnimation extends BaseAnimation {
    setup() {
        this.gif = new Image();
        this.gifLoaded = false;
        this.backgroundMode = 'black';
        this.gif.onload = () => {
            this.gifLoaded = true;
        };
        this.gif.src = '/backend-static/assets/animations/koi_pond_8bit_source.gif';
    }

    drawCoverImage(image) {
        const canvasRatio = this.canvas.width / this.canvas.height;
        const imageRatio = image.naturalWidth / image.naturalHeight;

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

        if (!this.gifLoaded) {
            return;
        }

        // Re-drawing the animated gif element each frame preserves the original motion.
        this.drawCoverImage(this.gif);
    }
}

if (typeof window !== 'undefined') {
    window.KoiPond8BitAnimation = KoiPond8BitAnimation;
}
