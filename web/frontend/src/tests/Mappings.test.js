const originalGetContext = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = jest.fn(() => null);

// eslint-disable-next-line global-require
const { normalizeScene } = require('../pages/Mappings');

afterAll(() => {
  HTMLCanvasElement.prototype.getContext = originalGetContext;
});

describe('normalizeScene', () => {
  test('normalizes legacy group and mask shapes for the mappings editor', () => {
    const normalized = normalizeScene({
      id: 1,
      name: 'Legacy Scene',
      masks: [
        {
          id: 'mask-1',
          name: 'Window',
          width: '1280',
          height: '720',
        },
      ],
      groups: [
        {
          id: 'group-1',
          maskIds: ['mask-1'],
          zIndex: '4',
          colorA: '#112233',
          colorB: '#445566',
          mediaDirectoryIds: ['5', 9, 'bad'],
        },
      ],
    });

    expect(normalized.masks[0]).toMatchObject({
      id: 'mask-1',
      name: 'Window',
      file_name: 'Window',
      width: 1280,
      height: 720,
    });
    expect(normalized.groups[0]).toMatchObject({
      id: 'group-1',
      name: 'Window',
      mask_ids: ['mask-1'],
      z_index: 4,
      color_a: '#112233',
      color_b: '#445566',
      media_directory_ids: [5, 9],
      visible: true,
      media_binding_type: 'video',
      transform: {
        scale: 1,
        offset_x: 0,
        offset_y: 0,
        rotation: 0,
      },
    });
  });

  test('fills safe defaults when scene arrays or names are missing', () => {
    const normalized = normalizeScene({
      groups: [
        {
          mask_id: 'solo-mask',
          visible: false,
        },
      ],
    });

    expect(normalized.name).toBe('Untitled Scene');
    expect(normalized.masks).toEqual([]);
    expect(normalized.groups[0]).toMatchObject({
      name: 'Group 1',
      mask_ids: ['solo-mask'],
      visible: false,
      color_a: '#b56a2d',
      color_b: '#6a7f58',
    });
  });
});
