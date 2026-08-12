import { defineModule } from '../defineModule';

export const xiaomiModule = defineModule({
  id: 'xiaomi',
  displayName: 'Xiaomi',
  kind: 'brand',
  recommendedTools: ['miflash'],
  aliases: ['xiaomi', 'redmi', 'poco'],
});
