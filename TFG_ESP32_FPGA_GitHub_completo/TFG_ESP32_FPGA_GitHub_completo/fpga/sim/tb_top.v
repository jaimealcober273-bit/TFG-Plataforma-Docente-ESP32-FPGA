`timescale 1ns / 1ps

module tb_top;

    reg CLK100MHZ = 0;
    reg esp32_tx = 1;   // UART en reposo = 1

    wire esp32_rx;
    wire [7:0] led;
    wire [7:0] an;
    wire [6:0] seg;
    wire dp;

    // Periodo de bit UART para 115200 baudios
    // 868 ciclos de reloj a 100 MHz
    localparam BIT_PERIOD = 8680; // ns

    // Instancia del DUT
    top dut (
        .CLK100MHZ(CLK100MHZ),
        .esp32_tx(esp32_tx),
        .esp32_rx(esp32_rx),
        .led(led),
        .an(an),
        .seg(seg),
        .dp(dp)
    );

    // Reloj de 100 MHz -> periodo de 10 ns
    always #5 CLK100MHZ = ~CLK100MHZ;

    // Tarea para enviar un byte UART: 115200 baudios, 8N1
    task send_uart_byte;
        input [7:0] data;
        integer i;
        begin

            // Bit de inicio
            esp32_tx = 0;
            #(BIT_PERIOD);

            // 8 bits de datos, LSB primero
            for (i = 0; i < 8; i = i + 1) begin
                esp32_tx = data[i];
                #(BIT_PERIOD);
            end

            // Bit de parada
            esp32_tx = 1;
            #(BIT_PERIOD);

        end
    endtask

    initial begin

        // Estado inicial
        esp32_tx = 1;
        #100000;

        // Enviar 0xAA = 10101010
        send_uart_byte(8'hAA);
        #100000;

        if (led == 8'hAA)
            $display("OK: recibido 0xAA");
        else
            $display("ERROR: esperado 0xAA, recibido %h", led);

        // Enviar 0x55 = 01010101
        send_uart_byte(8'h55);
        #100000;

        if (led == 8'h55)
            $display("OK: recibido 0x55");
        else
            $display("ERROR: esperado 0x55, recibido %h", led);

        // Enviar 0xFF
        send_uart_byte(8'hFF);
        #100000;

        if (led == 8'hFF)
            $display("OK: recibido 0xFF");
        else
            $display("ERROR: esperado 0xFF, recibido %h", led);

        // Enviar 0x00
        send_uart_byte(8'h00);
        #100000;

        if (led == 8'h00)
            $display("OK: recibido 0x00");
        else
            $display("ERROR: esperado 0x00, recibido %h", led);

        $stop;

    end

endmodule