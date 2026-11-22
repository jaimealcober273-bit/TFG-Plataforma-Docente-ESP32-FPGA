`timescale 1ns / 1ps

module tb_top;

    reg CLK100MHZ = 0;
    reg esp32_tx = 1;

    wire esp32_rx;
    wire [7:0] led;
    wire [7:0] an;
    wire [6:0] seg;
    wire dp;

    localparam BIT_PERIOD = 8680;

    top dut (
        .CLK100MHZ(CLK100MHZ),
        .esp32_tx(esp32_tx),
        .esp32_rx(esp32_rx),
        .led(led),
        .an(an),
        .seg(seg),
        .dp(dp)
    );

    always #5 CLK100MHZ = ~CLK100MHZ;

    task send_uart_byte;
        input [7:0] data;
        integer i;
        begin

            esp32_tx = 0;
            #(BIT_PERIOD);

            for (i = 0; i < 8; i = i + 1) begin
                esp32_tx = data[i];
                #(BIT_PERIOD);
            end

            esp32_tx = 1;
            #(BIT_PERIOD);

        end
    endtask

    initial begin

        esp32_tx = 1;
        #100000;

        send_uart_byte(8'hAA);
        #100000;

        if (led == 8'hAA)
            $display("OK: recibido 0xAA");
        else
            $display("ERROR: esperado 0xAA, recibido %h", led);

        send_uart_byte(8'h55);
        #100000;

        if (led == 8'h55)
            $display("OK: recibido 0x55");
        else
            $display("ERROR: esperado 0x55, recibido %h", led);

        send_uart_byte(8'hFF);
        #100000;

        if (led == 8'hFF)
            $display("OK: recibido 0xFF");
        else
            $display("ERROR: esperado 0xFF, recibido %h", led);

        send_uart_byte(8'h00);
        #100000;

        if (led == 8'h00)
            $display("OK: recibido 0x00");
        else
            $display("ERROR: esperado 0x00, recibido %h", led);

        $stop;

    end

endmodule
