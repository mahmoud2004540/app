import { defineModule } from '../defineModule';

export const qualcommModule = defineModule({
  id: 'qualcomm',
  displayName: 'Qualcomm',
  kind: 'platform',
  recommendedTools: ['qfil'],
  aliases: ['qualcomm', 'qcom', 'msm', 'sdm', 'sm6', 'sm7', 'sm8', 'snapdragon', 'kona', 'lito', 'bengal', 'lahaina'],
});
