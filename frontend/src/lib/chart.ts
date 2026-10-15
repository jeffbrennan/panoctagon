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
]);
export { init };
