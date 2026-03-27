// Fish Pond Animation - source-faithful canvas port of the CSS fish tank scene
class FishPondAnimation extends BaseAnimation {
    setup() {
        this.time = 0;
        this.fishProgress = 0;
        this.bubbleBoost = 1;
    }

    drawTankFrame() {
        const w = this.canvas.width;
        const h = this.canvas.height;
        const wall = Math.max(12, Math.min(w, h) * 0.03);

        this.ctx.fillStyle = '#191919';
        this.ctx.fillRect(0, 0, w, h);

        this.ctx.fillStyle = '#111';
        this.ctx.fillRect(w * 0.02, h * 0.04, w * 0.96, h * 0.88);

        const tankX = w * 0.08;
        const tankY = h * 0.08;
        const tankW = w * 0.84;
        const tankH = h * 0.74;

        this.ctx.fillStyle = '#0f1218';
        this.ctx.fillRect(tankX, tankY, tankW, tankH);

        const waterGradient = this.ctx.createLinearGradient(0, tankY, 0, tankY + tankH);
        waterGradient.addColorStop(0, 'rgba(220,220,220,0.32)');
        waterGradient.addColorStop(0.2, 'rgba(100,148,237,0.16)');
        waterGradient.addColorStop(1, 'rgba(40,74,115,0.46)');
        this.ctx.fillStyle = waterGradient;
        this.ctx.fillRect(tankX, tankY, tankW, tankH);

        this.ctx.strokeStyle = '#191919';
        this.ctx.lineWidth = wall;
        this.ctx.strokeRect(tankX, tankY, tankW, tankH);

        this.ctx.fillStyle = '#282320';
        this.ctx.fillRect(0, h * 0.82, w, h * 0.18);
    }

    drawGround() {
        const w = this.canvas.width;
        const h = this.canvas.height;
        const groundY = h * 0.67;
        const groundGradient = this.ctx.createLinearGradient(0, groundY, 0, h * 0.8);
        groundGradient.addColorStop(0, '#b19975');
        groundGradient.addColorStop(1, '#655848');
        this.ctx.fillStyle = groundGradient;
        this.ctx.fillRect(w * 0.08, groundY, w * 0.84, h * 0.11);
    }

    drawRock(x, y, rx, ry, fillA, fillB) {
        const grad = this.ctx.createLinearGradient(x - rx, y - ry, x + rx, y + ry);
        grad.addColorStop(0, fillA);
        grad.addColorStop(1, fillB);
        this.ctx.fillStyle = grad;
        this.ctx.beginPath();
        this.ctx.ellipse(x, y, rx, ry, 0.15, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.strokeStyle = 'rgba(37, 36, 36, 0.6)';
        this.ctx.lineWidth = 1.5;
        this.ctx.stroke();
    }

    drawRocks() {
        const w = this.canvas.width;
        const h = this.canvas.height;
        this.drawRock(w * 0.64, h * 0.62, w * 0.08, h * 0.11, '#956f53', '#604f46');
        this.drawRock(w * 0.73, h * 0.63, w * 0.09, h * 0.1, '#604f46', '#78604e');
        this.drawRock(w * 0.77, h * 0.71, w * 0.06, h * 0.05, '#956f53', '#78604e');
        this.drawRock(w * 0.32, h * 0.55, w * 0.06, h * 0.18, '#956f53', '#78604e');
        this.drawRock(w * 0.17, h * 0.69, w * 0.05, h * 0.08, '#956f53', '#78604e');
    }

    drawPlant(baseX, baseY, height, swing, colorA, colorB, width = 8) {
        this.ctx.save();
        this.ctx.strokeStyle = colorA;
        this.ctx.lineWidth = width;
        this.ctx.lineCap = 'round';
        this.ctx.beginPath();
        this.ctx.moveTo(baseX, baseY);
        this.ctx.quadraticCurveTo(baseX + swing * 0.4, baseY - height * 0.55, baseX + swing, baseY - height);
        this.ctx.stroke();

        this.ctx.strokeStyle = colorB;
        this.ctx.lineWidth = Math.max(3, width * 0.45);
        this.ctx.beginPath();
        this.ctx.moveTo(baseX, baseY - height * 0.28);
        this.ctx.quadraticCurveTo(baseX + swing * 0.15, baseY - height * 0.55, baseX + swing * 0.45, baseY - height * 0.82);
        this.ctx.stroke();
        this.ctx.restore();
    }

    drawPlants() {
        const w = this.canvas.width;
        const h = this.canvas.height;
        const t = this.time * 0.001;

        this.drawPlant(w * 0.74, h * 0.73, h * 0.26, Math.sin(t * 0.9) * 18 - 16, '#3d8f39', '#7fbf7f', 10);
        this.drawPlant(w * 0.79, h * 0.73, h * 0.21, Math.sin(t * 1.1 + 1) * 16 + 12, '#33852f', '#1e4e1d', 9);
        this.drawPlant(w * 0.13, h * 0.73, h * 0.18, Math.sin(t * 1.3 + 2) * 12 - 10, '#33852f', '#1e4e1d', 8);
        this.drawPlant(w * 0.18, h * 0.73, h * 0.15, Math.sin(t * 1.4 + 3) * 10 + 9, '#33852f', '#7fbf7f', 7);
        this.drawPlant(w * 0.47, h * 0.73, h * 0.34, Math.sin(t * 0.8 + 4) * 16 - 8, '#1e4e1d', '#7fbf7f', 11);
        this.drawPlant(w * 0.54, h * 0.73, h * 0.31, Math.sin(t * 0.7 + 5) * 18 + 8, '#1e4e1d', '#7fbf7f', 11);
    }

    drawBubbles() {
        const w = this.canvas.width;
        const h = this.canvas.height;
        const columns = [w * 0.11, w * 0.15, w * 0.2];
        columns.forEach((baseX, col) => {
            for (let i = 0; i < 7; i++) {
                const offset = (this.time * (0.025 + col * 0.005) * this.bubbleBoost + i * 82) % (h * 0.56);
                const y = h * 0.68 - offset;
                const x = baseX + Math.sin(this.time * 0.002 + i + col) * 7;
                const radius = 5 + (i % 3) * 2;
                this.ctx.strokeStyle = 'rgba(255,255,255,0.34)';
                this.ctx.lineWidth = 1.2;
                this.ctx.beginPath();
                this.ctx.arc(x, y, radius, 0, Math.PI * 2);
                this.ctx.stroke();
            }
        });
    }

    getFishPosition(progress) {
        const p = progress % 1;
        const anchors = [
            { x: 0.24, y: 0.45, flip: 1 },
            { x: 0.08, y: 0.42, flip: 1 },
            { x: 0.02, y: 0.42, flip: -1 },
            { x: 0.1, y: 0.34, flip: -1 },
            { x: 0.62, y: 0.46, flip: -1 },
            { x: 0.75, y: 0.56, flip: 1 },
            { x: 0.62, y: 0.64, flip: 1 },
            { x: 0.36, y: 0.62, flip: 1 },
            { x: 0.08, y: 0.62, flip: 1 },
            { x: 0.02, y: 0.45, flip: -1 },
            { x: 0.08, y: 0.36, flip: -1 },
            { x: 0.6, y: 0.28, flip: -1 },
            { x: 0.74, y: 0.28, flip: 1 },
            { x: 0.58, y: 0.45, flip: 1 },
            { x: 0.24, y: 0.45, flip: 1 },
        ];

        const scaled = p * (anchors.length - 1);
        const index = Math.floor(scaled);
        const nextIndex = Math.min(anchors.length - 1, index + 1);
        const mix = scaled - index;
        const current = anchors[index];
        const next = anchors[nextIndex];
        return {
            x: (current.x + (next.x - current.x) * mix) * this.canvas.width,
            y: (current.y + (next.y - current.y) * mix) * this.canvas.height,
            flip: mix < 0.5 ? current.flip : next.flip,
        };
    }

    drawFish() {
        this.fishProgress = (this.fishProgress + 0.00024) % 1;
        const pose = this.getFishPosition(this.fishProgress);
        const size = Math.min(this.canvas.width, this.canvas.height) * 0.11;
        const tailSwing = Math.sin(this.time * 0.012) * 0.35;
        const bodyBob = Math.sin(this.time * 0.01) * size * 0.02;

        this.ctx.save();
        this.ctx.translate(pose.x, pose.y + bodyBob);
        this.ctx.scale(pose.flip, 1);
        this.ctx.rotate(-0.62 + Math.sin(this.time * 0.003) * 0.08);

        const bodyGradient = this.ctx.createLinearGradient(-size * 0.4, -size * 0.2, size * 0.55, size * 0.45);
        bodyGradient.addColorStop(0, '#ff9800');
        bodyGradient.addColorStop(1, '#e88b00');
        this.ctx.fillStyle = bodyGradient;
        this.ctx.beginPath();
        this.ctx.ellipse(0, 0, size * 0.42, size * 0.26, 0.4, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.fillStyle = 'rgba(58,33,4,0.35)';
        for (let i = -1; i <= 1; i++) {
            this.ctx.beginPath();
            this.ctx.ellipse(size * 0.08 + i * size * 0.08, size * 0.03 + i * size * 0.02, size * 0.11, size * 0.055, 0.65, 0, Math.PI * 2);
            this.ctx.strokeStyle = 'rgba(67,40,1,0.55)';
            this.ctx.lineWidth = 1;
            this.ctx.stroke();
        }

        this.ctx.save();
        this.ctx.translate(size * 0.34, size * 0.12);
        this.ctx.rotate(tailSwing);
        this.ctx.fillStyle = '#e88b00';
        this.ctx.beginPath();
        this.ctx.moveTo(0, 0);
        this.ctx.quadraticCurveTo(size * 0.34, -size * 0.16, size * 0.38, 0);
        this.ctx.quadraticCurveTo(size * 0.34, size * 0.18, 0, size * 0.2);
        this.ctx.closePath();
        this.ctx.fill();
        this.ctx.restore();

        this.ctx.save();
        this.ctx.translate(size * 0.03, -size * 0.18);
        this.ctx.rotate(0.25);
        this.ctx.fillStyle = '#e88b00';
        this.ctx.beginPath();
        this.ctx.ellipse(0, 0, size * 0.12, size * 0.06, 0.2, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.restore();

        this.ctx.fillStyle = '#fcfcfc';
        this.ctx.beginPath();
        this.ctx.ellipse(-size * 0.13, -size * 0.07, size * 0.05, size * 0.1, 0.6, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.fillStyle = '#070707';
        this.ctx.beginPath();
        this.ctx.arc(-size * 0.12, -size * 0.03, Math.max(1.5, size * 0.012), 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.restore();
    }

    draw() {
        this.time += 16;
        this.drawTankFrame();
        this.drawGround();
        this.drawRocks();
        this.drawPlants();
        this.drawBubbles();
        this.drawFish();
    }

    onDataUpdate() {
        if (this.data.transit) {
            const count = Number(this.data.transit.count || (this.data.transit.activeRoutes || []).length || 0);
            this.bubbleBoost = 1 + Math.min(1.1, count * 0.08);
        }
    }
}

if (typeof window !== 'undefined') {
    window.FishPondAnimation = FishPondAnimation;
}
