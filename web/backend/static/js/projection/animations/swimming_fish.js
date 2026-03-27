// Swimming Fish Animation - internal canvas port inspired by simple SVG/CSS swimming fish studies
class SwimmingFishAnimation extends BaseAnimation {
    setup() {
        this.time = 0;
        this.fishes = Array.from({ length: 7 }, (_, index) => ({
            x: -120 - index * 110,
            y: this.canvas.height * (0.18 + (index % 5) * 0.14),
            speed: 1.2 + index * 0.18,
            scale: 0.55 + (index % 4) * 0.12,
            color: ['#4fc3f7', '#80cbc4', '#ffb74d', '#ce93d8'][index % 4],
            drift: Math.random() * Math.PI * 2,
        }));
        this.currentFlow = 1;
    }

    drawFish(fish) {
        const bodyLength = 82 * fish.scale;
        const bodyHeight = 34 * fish.scale;
        const tailSwing = Math.sin(this.time * 0.01 + fish.drift) * 0.42;

        this.ctx.save();
        this.ctx.translate(fish.x, fish.y + Math.sin(this.time * 0.002 + fish.drift) * 10);
        this.ctx.rotate(Math.sin(this.time * 0.004 + fish.drift) * 0.08);

        const bodyGradient = this.ctx.createLinearGradient(-bodyLength * 0.45, 0, bodyLength * 0.55, 0);
        bodyGradient.addColorStop(0, 'rgba(255,255,255,0.18)');
        bodyGradient.addColorStop(0.2, fish.color);
        bodyGradient.addColorStop(1, 'rgba(13, 45, 68, 0.8)');
        this.ctx.fillStyle = bodyGradient;
        this.ctx.beginPath();
        this.ctx.ellipse(0, 0, bodyLength * 0.5, bodyHeight * 0.7, 0, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.fillStyle = 'rgba(255,255,255,0.14)';
        this.ctx.beginPath();
        this.ctx.ellipse(bodyLength * 0.08, -bodyHeight * 0.12, bodyLength * 0.22, bodyHeight * 0.18, 0.2, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.save();
        this.ctx.translate(-bodyLength * 0.46, 0);
        this.ctx.rotate(tailSwing);
        this.ctx.fillStyle = fish.color;
        this.ctx.beginPath();
        this.ctx.moveTo(0, 0);
        this.ctx.lineTo(-bodyLength * 0.38, -bodyHeight * 0.48);
        this.ctx.lineTo(-bodyLength * 0.28, 0);
        this.ctx.lineTo(-bodyLength * 0.38, bodyHeight * 0.48);
        this.ctx.closePath();
        this.ctx.fill();
        this.ctx.restore();

        this.ctx.fillStyle = '#0b1624';
        this.ctx.beginPath();
        this.ctx.arc(bodyLength * 0.25, -bodyHeight * 0.08, Math.max(2, 2.8 * fish.scale), 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.strokeStyle = 'rgba(255,255,255,0.24)';
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.moveTo(bodyLength * 0.05, bodyHeight * 0.1);
        this.ctx.quadraticCurveTo(bodyLength * 0.18, bodyHeight * 0.2, bodyLength * 0.32, bodyHeight * 0.1);
        this.ctx.stroke();

        this.ctx.restore();
    }

    draw() {
        this.time += 16;

        const bg = this.ctx.createLinearGradient(0, 0, 0, this.canvas.height);
        bg.addColorStop(0, '#051b33');
        bg.addColorStop(1, '#0a5f7a');
        this.ctx.fillStyle = bg;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        for (let i = 0; i < 5; i++) {
            this.ctx.fillStyle = `rgba(255,255,255,${0.04 - i * 0.005})`;
            this.ctx.fillRect(
                0,
                this.canvas.height * (0.12 + i * 0.18) + Math.sin(this.time * 0.0015 + i) * 8,
                this.canvas.width,
                2 + i
            );
        }

        this.fishes.forEach((fish) => {
            fish.x += fish.speed * this.currentFlow;
            if (fish.x - 120 > this.canvas.width) {
                fish.x = -140;
                fish.y = this.canvas.height * (0.15 + Math.random() * 0.7);
            }
            this.drawFish(fish);
        });
    }

    onDataUpdate() {
        if (this.data.transit) {
            const count = Number(this.data.transit.count || (this.data.transit.activeRoutes || []).length || 0);
            this.currentFlow = 0.8 + Math.min(1.2, count * 0.08);
            this.fishes.forEach((fish, index) => {
                fish.speed = 1.1 + index * 0.18 + count * 0.03;
            });
        }
    }
}
