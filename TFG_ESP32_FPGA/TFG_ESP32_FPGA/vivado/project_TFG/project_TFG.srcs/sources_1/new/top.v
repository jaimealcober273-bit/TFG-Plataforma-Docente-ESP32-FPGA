module top (
    input  wire CLK100MHZ,
    input  wire esp32_tx,
    output wire esp32_rx,
    output reg  [7:0] led,
    output reg  [7:0] an,
    output reg  [6:0] seg,
    output wire dp
);

    parameter CLK_FREQ  = 100_000_000;
    parameter BAUD_RATE = 115200;

    localparam CLKS_PER_BIT = CLK_FREQ / BAUD_RATE;

    assign dp = 1'b1;

    function [7:0] bcdToDecimal;
        input [7:0] bcd;
        begin
            bcdToDecimal = (bcd[7:4] * 10) + bcd[3:0];
        end
    endfunction

    function [7:0] decimalToBCD;
        input [7:0] valor;
        reg [7:0] valor_limitado;
        begin

            if (valor > 99)
                valor_limitado = 99;
            else
                valor_limitado = valor;

            decimalToBCD =
                ((valor_limitado / 10) << 4) |
                (valor_limitado % 10);

        end
    endfunction

    reg [31:0] rx_clk_count = 0;
    reg [2:0]  rx_bit_index = 0;
    reg [7:0]  rx_shift = 0;
    reg [7:0]  rx_byte = 0;
    reg [1:0]  rx_state = 0;

    localparam RX_IDLE  = 2'd0;
    localparam RX_START = 2'd1;
    localparam RX_DATA  = 2'd2;
    localparam RX_STOP  = 2'd3;

    reg [7:0] temp1_bcd = 8'h00;

    reg [7:0] temp2_bcd = 8'h00;

    reg [7:0] hum_bcd = 8'h00;

    reg [7:0] temp_max_bcd   = 8'h00;
    reg [7:0] temp_min_bcd   = 8'h00;
    reg [7:0] temp_media_bcd = 8'h00;

    wire [7:0] temp1_decimal;
    wire [7:0] temp2_decimal;

    assign temp1_decimal = bcdToDecimal(temp1_bcd);
    assign temp2_decimal = bcdToDecimal(temp2_bcd);

    wire [8:0] suma_temperaturas;

    assign suma_temperaturas =
        {1'b0, temp1_decimal} +
        {1'b0, temp2_decimal};

    wire [7:0] media_decimal;

    assign media_decimal = suma_temperaturas >> 1;

    wire [7:0] calculo_max_bcd;
    wire [7:0] calculo_min_bcd;
    wire [7:0] calculo_media_bcd;

    assign calculo_max_bcd =
        (temp1_decimal >= temp2_decimal) ?
        temp1_bcd :
        temp2_bcd;

    assign calculo_min_bcd =
        (temp1_decimal <= temp2_decimal) ?
        temp1_bcd :
        temp2_bcd;

    assign calculo_media_bcd =
        decimalToBCD(media_decimal);

    reg [1:0] rx_select = 2'd0;

    reg datos_completos_pulse = 1'b0;

    reg [7:0] reply_max_bcd   = 8'h00;
    reg [7:0] reply_min_bcd   = 8'h00;
    reg [7:0] reply_media_bcd = 8'h00;
    reg [7:0] reply_hum_bcd   = 8'h00;

    always @(posedge CLK100MHZ) begin

        datos_completos_pulse <= 1'b0;

        case (rx_state)

            RX_IDLE: begin

                rx_clk_count <= 0;
                rx_bit_index <= 0;

                if (esp32_tx == 1'b0)
                    rx_state <= RX_START;

            end

            RX_START: begin

                if (rx_clk_count == (CLKS_PER_BIT / 2)) begin

                    rx_clk_count <= 0;

                    if (esp32_tx == 1'b0)
                        rx_state <= RX_DATA;
                    else
                        rx_state <= RX_IDLE;

                end
                else begin
                    rx_clk_count <= rx_clk_count + 1;
                end

            end

            RX_DATA: begin

                if (rx_clk_count == CLKS_PER_BIT - 1) begin

                    rx_clk_count <= 0;

                    rx_shift[rx_bit_index] <= esp32_tx;

                    if (rx_bit_index == 7) begin

                        rx_bit_index <= 0;
                        rx_state <= RX_STOP;

                    end
                    else begin

                        rx_bit_index <= rx_bit_index + 1;

                    end

                end
                else begin

                    rx_clk_count <= rx_clk_count + 1;

                end

            end

            RX_STOP: begin

                if (rx_clk_count == CLKS_PER_BIT - 1) begin

                    rx_clk_count <= 0;
                    rx_state <= RX_IDLE;

                    if (esp32_tx == 1'b1) begin

                        rx_byte <= rx_shift;

                        led <= rx_shift;

                        if (rx_select == 2'd0) begin

                            temp1_bcd <= rx_shift;
                            rx_select <= 2'd1;

                        end

                        else if (rx_select == 2'd1) begin

                            temp2_bcd <= rx_shift;
                            rx_select <= 2'd2;

                        end

                        else begin

                            hum_bcd <= rx_shift;
                            rx_select <= 2'd0;

                            temp_max_bcd   <= calculo_max_bcd;
                            temp_min_bcd   <= calculo_min_bcd;
                            temp_media_bcd <= calculo_media_bcd;

                            reply_max_bcd   <= calculo_max_bcd;
                            reply_min_bcd   <= calculo_min_bcd;
                            reply_media_bcd <= calculo_media_bcd;
                            reply_hum_bcd   <= rx_shift;

                            datos_completos_pulse <= 1'b1;

                        end

                    end

                end
                else begin

                    rx_clk_count <= rx_clk_count + 1;

                end

            end

            default: begin

                rx_state <= RX_IDLE;

            end

        endcase
    end

    localparam TX_IDLE  = 3'd0;
    localparam TX_START = 3'd1;
    localparam TX_DATA  = 3'd2;
    localparam TX_STOP  = 3'd3;

    reg [2:0] tx_state = TX_IDLE;

    reg [31:0] tx_clk_count = 0;
    reg [2:0] tx_bit_index = 0;

    reg [7:0] tx_shift = 8'h00;

    reg tx_line = 1'b1;
    reg tx_busy = 1'b0;
    reg tx_done = 1'b0;

    reg tx_start = 1'b0;
    reg [7:0] tx_data = 8'h00;

    assign esp32_rx = tx_line;

    always @(posedge CLK100MHZ) begin

        tx_done <= 1'b0;

        case (tx_state)

            TX_IDLE: begin

                tx_line <= 1'b1;
                tx_clk_count <= 0;
                tx_bit_index <= 0;
                tx_busy <= 1'b0;

                if (tx_start == 1'b1) begin

                    tx_busy <= 1'b1;
                    tx_shift <= tx_data;

                    tx_line <= 1'b0;

                    tx_state <= TX_START;

                end

            end

            TX_START: begin

                tx_busy <= 1'b1;
                tx_line <= 1'b0;

                if (tx_clk_count == CLKS_PER_BIT - 1) begin

                    tx_clk_count <= 0;
                    tx_state <= TX_DATA;

                end
                else begin

                    tx_clk_count <= tx_clk_count + 1;

                end

            end

            TX_DATA: begin

                tx_busy <= 1'b1;

                tx_line <= tx_shift[tx_bit_index];

                if (tx_clk_count == CLKS_PER_BIT - 1) begin

                    tx_clk_count <= 0;

                    if (tx_bit_index == 7) begin

                        tx_bit_index <= 0;
                        tx_state <= TX_STOP;

                    end
                    else begin

                        tx_bit_index <= tx_bit_index + 1;

                    end

                end
                else begin

                    tx_clk_count <= tx_clk_count + 1;

                end

            end

            TX_STOP: begin

                tx_busy <= 1'b1;

                tx_line <= 1'b1;

                if (tx_clk_count == CLKS_PER_BIT - 1) begin

                    tx_clk_count <= 0;
                    tx_done <= 1'b1;
                    tx_state <= TX_IDLE;

                end
                else begin

                    tx_clk_count <= tx_clk_count + 1;

                end

            end

            default: begin

                tx_state <= TX_IDLE;
                tx_line <= 1'b1;
                tx_busy <= 1'b0;

            end

        endcase
    end

    localparam REPLY_IDLE       = 3'd0;
    localparam REPLY_WAIT_MAX   = 3'd1;
    localparam REPLY_WAIT_MIN   = 3'd2;
    localparam REPLY_WAIT_MEDIA = 3'd3;
    localparam REPLY_WAIT_HUM   = 3'd4;

    reg [2:0] reply_state = REPLY_IDLE;

    reg pending_reply = 1'b0;

    always @(posedge CLK100MHZ) begin

        tx_start <= 1'b0;

        if (datos_completos_pulse == 1'b1) begin

            pending_reply <= 1'b1;

        end

        case (reply_state)

            REPLY_IDLE: begin

                if ((pending_reply == 1'b1) &&
                    (tx_busy == 1'b0)) begin

                    tx_data <= reply_max_bcd;
                    tx_start <= 1'b1;

                    reply_state <= REPLY_WAIT_MAX;

                end

            end

            REPLY_WAIT_MAX: begin

                if (tx_done == 1'b1) begin

                    tx_data <= reply_min_bcd;
                    tx_start <= 1'b1;

                    reply_state <= REPLY_WAIT_MIN;

                end

            end

            REPLY_WAIT_MIN: begin

                if (tx_done == 1'b1) begin

                    tx_data <= reply_media_bcd;
                    tx_start <= 1'b1;

                    reply_state <= REPLY_WAIT_MEDIA;

                end

            end

            REPLY_WAIT_MEDIA: begin

                if (tx_done == 1'b1) begin

                    tx_data <= reply_hum_bcd;
                    tx_start <= 1'b1;

                    reply_state <= REPLY_WAIT_HUM;

                end

            end

            REPLY_WAIT_HUM: begin

                if (tx_done == 1'b1) begin

                    pending_reply <= 1'b0;
                    reply_state <= REPLY_IDLE;

                end

            end

            default: begin

                reply_state <= REPLY_IDLE;

            end

        endcase
    end

    wire [3:0] temp_tens;
    wire [3:0] temp_units;

    wire [3:0] hum_tens;
    wire [3:0] hum_units;

    assign temp_tens  = temp_media_bcd[7:4];
    assign temp_units = temp_media_bcd[3:0];

    assign hum_tens   = hum_bcd[7:4];
    assign hum_units  = hum_bcd[3:0];

    reg [18:0] refresh = 0;
    reg [1:0] display_sel = 0;
    reg [3:0] digit;

    always @(posedge CLK100MHZ) begin

        refresh <= refresh + 1;

        display_sel <= refresh[18:17];

        case (refresh[18:17])

            2'd0: begin

                an <= 8'b11111110;
                digit <= hum_units;

            end

            2'd1: begin

                an <= 8'b11111101;
                digit <= hum_tens;

            end

            2'd2: begin

                an <= 8'b11111011;
                digit <= temp_units;

            end

            2'd3: begin

                an <= 8'b11110111;
                digit <= temp_tens;

            end

            default: begin

                an <= 8'b11111111;
                digit <= 4'd0;

            end

        endcase
    end

    always @(*) begin

        case (digit)

            4'h0: seg = 7'b1000000;
            4'h1: seg = 7'b1111001;
            4'h2: seg = 7'b0100100;
            4'h3: seg = 7'b0110000;
            4'h4: seg = 7'b0011001;
            4'h5: seg = 7'b0010010;
            4'h6: seg = 7'b0000010;
            4'h7: seg = 7'b1111000;
            4'h8: seg = 7'b0000000;
            4'h9: seg = 7'b0010000;

            default:
                seg = 7'b1111111;

        endcase
    end

endmodule
