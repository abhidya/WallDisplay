// Pokedex Animation - source-faithful canvas port of the CSS pokedex layout
class PokedexAnimation extends BaseAnimation {
    setup() {
        this.time = 0;
        this.sprite = new Image();
        this.spriteLoaded = false;
        this.sprite.onload = () => {
            this.spriteLoaded = true;
        };
        this.sprite.src = '/backend-static/assets/animations/pokedex_psyduck.gif';
    }

    roundRect(x, y, w, h, r) {
        const radius = Math.min(r, w * 0.5, h * 0.5);
        this.ctx.beginPath();
        this.ctx.moveTo(x + radius, y);
        this.ctx.arcTo(x + w, y, x + w, y + h, radius);
        this.ctx.arcTo(x + w, y + h, x, y + h, radius);
        this.ctx.arcTo(x, y + h, x, y, radius);
        this.ctx.arcTo(x, y, x + w, y, radius);
        this.ctx.closePath();
    }

    drawButton(x, y, r, inner, outer, shadow) {
        this.ctx.save();
        this.ctx.translate(x, y);
        this.ctx.shadowColor = shadow || 'rgba(73,0,0,0.5)';
        this.ctx.shadowBlur = r * 0.4;
        const grad = this.ctx.createRadialGradient(-r * 0.25, -r * 0.25, r * 0.2, 0, 0, r);
        grad.addColorStop(0, inner);
        grad.addColorStop(1, outer);
        this.ctx.fillStyle = grad;
        this.ctx.beginPath();
        this.ctx.arc(0, 0, r, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.restore();
    }

    drawScreen(screenX, screenY, screenW, screenH) {
        this.ctx.fillStyle = '#b0b0b0';
        this.roundRect(screenX, screenY, screenW, screenH, 18);
        this.ctx.fill();

        const pictureX = screenX + screenW * 0.08;
        const pictureY = screenY + screenH * 0.12;
        const pictureW = screenW * 0.84;
        const pictureH = screenH * 0.72;

        this.ctx.fillStyle = '#ffffff';
        this.ctx.strokeStyle = '#494949';
        this.ctx.lineWidth = 3;
        this.roundRect(pictureX, pictureY, pictureW, pictureH, 14);
        this.ctx.fill();
        this.ctx.stroke();

        if (this.spriteLoaded) {
            const ratio = this.sprite.naturalWidth / this.sprite.naturalHeight;
            let drawW = pictureW * 0.84;
            let drawH = drawW / ratio;
            if (drawH > pictureH * 0.9) {
                drawH = pictureH * 0.9;
                drawW = drawH * ratio;
            }
            this.ctx.drawImage(
                this.sprite,
                pictureX + (pictureW - drawW) * 0.5,
                pictureY + (pictureH - drawH) * 0.5,
                drawW,
                drawH
            );
        }

        this.drawButton(screenX + screenW * 0.14, screenY + screenH * 0.88, screenW * 0.045, '#c00d0d', '#8b0000');

        this.ctx.fillStyle = '#494949';
        for (let i = 0; i < 4; i += 1) {
            this.roundRect(screenX + screenW * 0.68, screenY + screenH * (0.83 + i * 0.03), screenW * 0.16, screenH * 0.012, 3);
            this.ctx.fill();
        }

        this.drawButton(screenX + screenW * 0.12, screenY + screenH * 0.05, screenW * 0.018, '#c00d0d', '#8b0000', 'transparent');
        this.drawButton(screenX + screenW * 0.2, screenY + screenH * 0.05, screenW * 0.018, '#c00d0d', '#8b0000', 'transparent');
    }

    drawDPad(x, y, size) {
        const arm = size * 0.34;
        const thickness = size * 0.28;
        this.ctx.fillStyle = '#222';
        this.roundRect(x - thickness * 0.5, y - arm - thickness * 0.5, thickness, arm * 2 + thickness, 5);
        this.ctx.fill();
        this.roundRect(x - arm - thickness * 0.5, y - thickness * 0.5, arm * 2 + thickness, thickness, 5);
        this.ctx.fill();
        this.drawButton(x, y, thickness * 0.28, '#111', '#222', 'transparent');
    }

    drawRightPanel(rightX, topY, rightW, shellH) {
        const statsX = rightX + rightW * 0.08;
        const statsY = topY + shellH * 0.26;
        const statsW = rightW * 0.8;
        const statsH = shellH * 0.24;

        this.ctx.fillStyle = '#30da0c';
        this.roundRect(statsX, statsY, statsW, statsH, 14);
        this.ctx.fill();

        this.ctx.fillStyle = '#163300';
        this.ctx.font = `${Math.max(10, rightW * 0.038)}px Arial`;
        this.ctx.textBaseline = 'top';
        const lines = [
            'Name: Psyduck',
            'Type: Water',
            "Height: 2'07''",
            'Weight: 43.2 lbs.',
            '',
            'The duck Pokemon',
            'Uses mysterious powers',
            'to perform attacks.',
        ];
        lines.forEach((line, index) => {
            this.ctx.fillText(line, statsX + statsW * 0.06, statsY + statsH * 0.08 + index * rightW * 0.045);
        });

        const buttonRows = [0.6, 0.69];
        buttonRows.forEach((rowY) => {
            for (let i = 0; i < 5; i += 1) {
                const bx = rightX + rightW * (0.14 + i * 0.13);
                const by = topY + shellH * rowY;
                this.ctx.fillStyle = '#0530e5';
                this.roundRect(bx, by, rightW * 0.1, shellH * 0.065, 6);
                this.ctx.fill();
            }
        });

        this.drawButton(rightX + rightW * 0.1, topY + shellH * 0.79, rightW * 0.018, '#ff9b5b', '#fb6505', 'transparent');
        this.drawButton(rightX + rightW * 0.17, topY + shellH * 0.79, rightW * 0.018, '#0abd0a', '#057b05', 'transparent');

        this.ctx.fillStyle = '#057b05';
        this.roundRect(rightX + rightW * 0.56, topY + shellH * 0.78, rightW * 0.14, shellH * 0.025, 5);
        this.ctx.fill();
        this.ctx.fillStyle = '#bb0505';
        this.roundRect(rightX + rightW * 0.73, topY + shellH * 0.78, rightW * 0.14, shellH * 0.025, 5);
        this.ctx.fill();

        this.ctx.fillStyle = '#ffff00';
        this.roundRect(rightX + rightW * 0.08, topY + shellH * 0.86, rightW * 0.36, shellH * 0.1, 10);
        this.ctx.fill();
        this.roundRect(rightX + rightW * 0.54, topY + shellH * 0.86, rightW * 0.36, shellH * 0.1, 10);
        this.ctx.fill();
    }

    draw() {
        this.time += 16;

        const w = this.canvas.width;
        const h = this.canvas.height;
        this.ctx.fillStyle = '#ffffff';
        this.ctx.fillRect(0, 0, w, h);

        const scale = Math.min(w / 750, h / 500);
        const totalW = 750 * scale;
        const totalH = 500 * scale;
        const originX = (w - totalW) * 0.5;
        const originY = (h - totalH) * 0.5;

        const leftW = 400 * scale;
        const rightW = 350 * scale;
        const shellH = totalH;

        // Left shell
        this.ctx.fillStyle = '#8b0000';
        this.roundRect(originX, originY, leftW, shellH * 0.16, 26 * scale);
        this.ctx.fill();
        this.ctx.fillStyle = '#c00d0d';
        this.roundRect(originX, originY + shellH * 0.11, leftW, shellH * 0.84, 26 * scale);
        this.ctx.fill();

        // Top controls
        this.drawButton(originX + leftW * 0.12, originY + shellH * 0.09, leftW * 0.075, '#05fbfb', '#29abe3');
        this.ctx.fillStyle = 'rgba(255,255,255,0.6)';
        this.roundRect(originX + leftW * 0.105, originY + shellH * 0.055, leftW * 0.05, shellH * 0.028, 8 * scale);
        this.ctx.fill();
        this.drawButton(originX + leftW * 0.26, originY + shellH * 0.085, leftW * 0.025, '#fb7b7b', '#fb0505');
        this.drawButton(originX + leftW * 0.32, originY + shellH * 0.085, leftW * 0.025, '#fbfb9b', '#fbfb05');
        this.drawButton(originX + leftW * 0.38, originY + shellH * 0.085, leftW * 0.025, '#b0fb7b', '#50fb05');

        // Screen
        this.drawScreen(originX + leftW * 0.05, originY + shellH * 0.26, leftW * 0.68, shellH * 0.49);

        // Lower left controls
        this.drawButton(originX + leftW * 0.11, originY + shellH * 0.84, leftW * 0.065, '#307bfb', '#0530e5');
        this.ctx.fillStyle = '#057b05';
        this.roundRect(originX + leftW * 0.22, originY + shellH * 0.81, leftW * 0.13, shellH * 0.026, 6 * scale);
        this.ctx.fill();
        this.ctx.fillStyle = '#bb0505';
        this.roundRect(originX + leftW * 0.385, originY + shellH * 0.81, leftW * 0.13, shellH * 0.026, 6 * scale);
        this.ctx.fill();
        this.drawDPad(originX + leftW * 0.69, originY + shellH * 0.87, leftW * 0.22);

        // Right shell
        const rightX = originX + leftW;
        this.ctx.fillStyle = '#c00d0d';
        this.roundRect(rightX, originY + shellH * 0.11, rightW, shellH * 0.84, 26 * scale);
        this.ctx.fill();
        this.ctx.fillStyle = '#ffffff';
        this.roundRect(rightX + rightW * 0.45, originY, rightW * 0.55, shellH * 0.2, 24 * scale);
        this.ctx.fill();
        this.drawRightPanel(rightX, originY, rightW, shellH);
    }
}

if (typeof window !== 'undefined') {
    window.PokedexAnimation = PokedexAnimation;
}
