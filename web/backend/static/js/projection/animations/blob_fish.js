// Blob Fish Animation - source-faithful canvas port of the CSS blob fish
class BlobFishAnimation extends BaseAnimation {
    setup() {
        this.time = 0;
        this.waterTop = '#0d0a42';
        this.waterBottom = '#030032';
        this.baseScale = 1;
    }

    drawFish() {
        const size = Math.min(this.canvas.width, this.canvas.height) * 0.58 * this.baseScale;
        const faceWidth = size * 0.5;
        const faceHeight = size * 0.38;
        const bodyY = this.canvas.height * 0.52 + Math.sin(this.time * 0.0018) * (size * 0.03);
        const bodyX = this.canvas.width * 0.5;
        const facePulse = 0.72 + Math.sin(this.time * 0.0015) * 0.08;
        const finSwing = Math.sin(this.time * 0.003) * 0.35;

        this.ctx.save();
        this.ctx.translate(bodyX, bodyY);

        const faceGradient = this.ctx.createLinearGradient(0, -faceHeight * 0.5, 0, faceHeight * 0.5);
        faceGradient.addColorStop(0, '#dc9997');
        faceGradient.addColorStop(1, '#927dad');
        this.ctx.fillStyle = faceGradient;

        this.ctx.beginPath();
        this.ctx.moveTo(-faceWidth * 0.5, -faceHeight * 0.15);
        this.ctx.bezierCurveTo(-faceWidth * 0.48, -faceHeight * facePulse, faceWidth * 0.48, -faceHeight * facePulse, faceWidth * 0.5, -faceHeight * 0.15);
        this.ctx.bezierCurveTo(faceWidth * 0.56, faceHeight * 0.5, faceWidth * 0.2, faceHeight * 0.62, 0, faceHeight * 0.58);
        this.ctx.bezierCurveTo(-faceWidth * 0.2, faceHeight * 0.62, -faceWidth * 0.56, faceHeight * 0.5, -faceWidth * 0.5, -faceHeight * 0.15);
        this.ctx.closePath();
        this.ctx.fill();

        this.ctx.save();
        this.ctx.translate(-faceWidth * 0.54, faceHeight * 0.1);
        this.ctx.rotate(0.2 + finSwing);
        this.ctx.fillStyle = '#ae88a5';
        this.ctx.beginPath();
        this.ctx.ellipse(0, 0, faceWidth * 0.14, faceHeight * 0.09, 0.2, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.restore();

        this.ctx.save();
        this.ctx.translate(faceWidth * 0.54, faceHeight * 0.1);
        this.ctx.rotate(-0.2 - finSwing);
        this.ctx.fillStyle = '#ae88a5';
        this.ctx.beginPath();
        this.ctx.ellipse(0, 0, faceWidth * 0.14, faceHeight * 0.09, -0.2, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.restore();

        this.ctx.fillStyle = '#dc9997';
        this.ctx.beginPath();
        this.ctx.ellipse(0, faceHeight * 0.18, faceWidth * 0.25, faceHeight * 0.17, 0, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.fillStyle = '#231119';
        this.ctx.beginPath();
        this.ctx.ellipse(-faceWidth * 0.17, faceHeight * 0.18, faceWidth * 0.03, faceHeight * 0.05, 0.2, 0, Math.PI * 2);
        this.ctx.ellipse(faceWidth * 0.17, faceHeight * 0.18, faceWidth * 0.03, faceHeight * 0.05, -0.2, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.fillStyle = '#ae88a5';
        this.ctx.beginPath();
        this.ctx.ellipse(0, faceHeight * 0.33, faceWidth * 0.3, faceHeight * 0.08, 0, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.strokeStyle = '#4f2744';
        this.ctx.lineWidth = Math.max(2, size * 0.009);
        this.ctx.beginPath();
        this.ctx.arc(0, faceHeight * 0.34, faceWidth * 0.24, 0.08 * Math.PI, 0.92 * Math.PI, false);
        this.ctx.stroke();

        this.ctx.restore();
    }

    draw() {
        this.time += 16;

        const bg = this.ctx.createLinearGradient(0, 0, 0, this.canvas.height);
        bg.addColorStop(0, this.waterTop);
        bg.addColorStop(1, this.waterBottom);
        this.ctx.fillStyle = bg;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        this.drawFish();
    }

    onDataUpdate() {
        if (this.data.weather) {
            const humidity = Number(this.data.weather.humidity || 50);
            this.baseScale = 0.94 + Math.min(0.16, humidity / 500);
        }
    }
}

if (typeof window !== 'undefined') {
    window.BlobFishAnimation = BlobFishAnimation;
}
