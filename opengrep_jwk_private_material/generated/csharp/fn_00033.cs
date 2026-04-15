using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"opcHX0-VM289","alg":"RS256","n":"UdpCSILd6LgANaGinnN2i_EdhI1dIzwAjBZt9X078WDMMNQw","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"opcHX0-VM289\",\"alg\":\"RS256\",\"n\":\"UdpCSILd6LgANaGinnN2i_EdhI1dIzwAjBZt9X078WDMMNQw\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
