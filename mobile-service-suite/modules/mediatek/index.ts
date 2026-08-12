import { defineModule } from '../defineModule';

export const mediatekModule = defineModule({
  id: 'mediatek',
  displayName: 'MediaTek',
  kind: 'platform',
  recommendedTools: ['spflash'],
  aliases: ['mediatek', 'mtk', 'mt6', 'mt8', 'helio', 'dimensity'],
});
