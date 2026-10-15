import { init, use } from 'echarts/core';
import { TooltipComponent, LegendComponent, AriaComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

use([TooltipComponent, LegendComponent, AriaComponent, CanvasRenderer]);
export { init };
