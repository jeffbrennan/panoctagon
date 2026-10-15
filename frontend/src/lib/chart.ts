import { init, use } from 'echarts/core';
import { BarChart, LineChart, ScatterChart, GraphChart, BoxplotChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  AriaComponent,
  VisualMapComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { LabelLayout } from 'echarts/features';

use([
  BarChart,
  LineChart,
  ScatterChart,
  GraphChart,
  BoxplotChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  AriaComponent,
  VisualMapComponent,
  CanvasRenderer,
  LabelLayout,
]);
export { init };
